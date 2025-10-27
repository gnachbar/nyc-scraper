/**
 * Brooklyn Academy of Music (BAM) Scraper
 * 
 * Scrapes events from Brooklyn Academy of Music website
 * Uses multi-section approach: iterate through Music, Theater, Dance, Talks, Opera, Poetry, Kids, Performance Art, Holiday
 * 
 * Key Features:
 * - Uses shared utility functions from src/lib/ to reduce code duplication
 * - Single-venue scraper (hardcodes 'Brooklyn Academy of Music' as eventLocation)
 * - Multi-section extraction: iterates through 9 different event categories
 * - Pagination via right arrow buttons in each section
 * - Date range expansion: creates individual events for each day in a date range
 * - Automatically saves to database and runs consistency tests
 * 
 * Sections scraped:
 * - Music
 * - Theater
 * - Dance
 * - Talks
 * - Opera
 * - Poetry
 * - Kids
 * - Performance Art
 * - Holiday
 */

// Import shared utilities from src/lib/
import { initStagehand, openBrowserbaseSession } from '../lib/scraper-utils.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';
import { z } from 'zod';

/**
 * Expand date ranges into individual dates
 * Handles formats like "Oct 21—Oct 25, 2025" or "Dec 5—Dec 7, 2025"
 * Also normalizes dates like "Sat, Nov 15, 2025" to "Saturday, November 15, 2025"
 * @param {string} dateRange - Date range string
 * @returns {Array<string>} Array of individual date strings
 */
function expandDateRange(dateRange) {
  // First, normalize single dates that have day-of-week prefix
  // e.g., "Sat, Nov 15, 2025" -> "Saturday, November 15, 2025"
  let normalizedDate = dateRange;
  try {
    // Try to parse and reformat if it's a single date with day prefix
    const parsedDate = new Date(dateRange);
    if (!isNaN(parsedDate.getTime())) {
      normalizedDate = parsedDate.toLocaleDateString('en-US', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      });
    }
  } catch (e) {
    // Not a parseable date, continue
  }
  
  // Check if this is a date range (contains —)
  if (!normalizedDate.includes('—')) {
    return [normalizedDate]; // Single date, return normalized version
  }

  const dates = [];
  
  try {
    // Parse date range like "Oct 21—Oct 25, 2025"
    const parts = normalizedDate.split('—');
    if (parts.length !== 2) {
      return [normalizedDate]; // Malformed, return as-is
    }

    const startDateStr = parts[0].trim();
    const endDateStr = parts[1].trim();

    // Extract year from end date
    const yearMatch = endDateStr.match(/(\d{4})/);
    const year = yearMatch ? yearMatch[1] : new Date().getFullYear();

    // Parse start date
    const startDate = new Date(`${startDateStr}, ${year}`);
    const endDate = new Date(`${endDateStr}`);

    // Generate all dates in range
    const currentDate = new Date(startDate);
    while (currentDate <= endDate) {
      const dateStr = currentDate.toLocaleDateString('en-US', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      });
      dates.push(dateStr);
      currentDate.setDate(currentDate.getDate() + 1);
    }
  } catch (error) {
    console.warn(`Failed to expand date range "${dateRange}": ${error.message}`);
    return [normalizedDate]; // Return normalized version on error
  }

  return dates;
}

/**
 * Extract events from a single section
 * @param {Object} page - Stagehand page object
 * @param {string} sectionName - Name of the section to extract from
 * @returns {Promise<Array>} Array of extracted events
 */
async function extractEventsFromSection(page, sectionName) {
  const sectionEvents = [];
  
  console.log(`\n=== Extracting events from ${sectionName} section ===`);
  
  // Schema for extracting events from a section
  const sectionEventSchema = z.object({
    events: z.array(z.object({
      eventName: z.string(),
      eventDate: z.string(), // Can be single date or date range
      eventTime: z.string().default(""),
      eventUrl: z.string(), // Temporarily not validating as URL to debug
      eventLocation: z.string().default("Brooklyn Academy of Music")
    }))
  });

  let pageCount = 0;
  const maxPages = 20; // Safety limit for pagination
  const seenEventKeys = new Set(); // Track seen events to detect loops

  while (pageCount < maxPages) {
    console.log(`Extracting ${sectionName} events from page ${pageCount + 1}...`);
    
    try {
      // Extract events from current view - be VERY specific to extract ONLY from this section
      const result = await page.extract({
        instruction: `Extract ONLY the events that appear in the horizontal carousel/slider section with the heading "${sectionName}". 
        
Do NOT extract events from any other section on the page. Only extract events from the row of event cards that are directly associated with the "${sectionName}" heading.

For each event card in the ${sectionName} section, get:
- eventName: The full name/title of the event
- eventDate: The FULL date including day, month, and YEAR. This can be a single date (e.g., "Monday, October 27, 2025") or a date range (e.g., "Oct 21—Oct 25, 2025" or "Dec 5—Dec 7, 2025")
- eventTime: The time of the event if available, otherwise empty string
- eventUrl: The complete URL to the event page (must be a full URL starting with https://www.bam.org/)
- eventLocation: Set to 'Brooklyn Academy of Music' for all events

IMPORTANT: 
- For eventUrl, extract the href attribute from the event's main link/title
- Do NOT use "https://www.bam.org/more" or other navigation links
- If the URL is relative (starts with /), prepend "https://www.bam.org"
- ONLY extract events from the ${sectionName} section's carousel, ignore all other sections

Return only the events from the ${sectionName} section as an array.`,
        schema: sectionEventSchema
      });

      console.log(`Found ${result.events.length} events on ${sectionName} page ${pageCount + 1}`);
      
      // Check for duplicate events (pagination loop detection)
      let newEventsCount = 0;
      for (const event of result.events) {
        const key = `${event.eventName}|${event.eventDate}`;
        if (!seenEventKeys.has(key)) {
          seenEventKeys.add(key);
          newEventsCount++;
        }
      }
      
      if (newEventsCount === 0 && result.events.length > 0) {
        console.log(`⚠ WARNING: All events on this page have been seen before. Pagination may be stuck or looping.`);
        break; // Stop pagination if we're seeing duplicates
      }
      
      console.log(`  New events: ${newEventsCount}, Previously seen: ${result.events.length - newEventsCount}`);
      sectionEvents.push(...result.events);

      // Try to click the right arrow for this section
      try {
        const [arrowAction] = await page.observe(`click the right arrow button to the right of the ${sectionName} section`);
        
        if (arrowAction) {
          await page.act(arrowAction);
          pageCount++;
          console.log(`Successfully clicked right arrow for ${sectionName} (page ${pageCount + 1})`);
          
          // Wait for new content to load
          await page.waitForTimeout(3000);
        } else {
          console.log(`No more right arrow found for ${sectionName}. Section complete.`);
          break;
        }
      } catch (arrowError) {
        console.log(`Could not find or click right arrow for ${sectionName}: ${arrowError.message}`);
        
        // If browser is closed, break out of the loop
        if (arrowError.message.includes('closed') || arrowError.message.includes('Target page')) {
          console.error('Browser context closed during pagination.');
          break;
        }
        
        break;
      }
    } catch (extractError) {
      console.error(`Failed to extract events from ${sectionName} page ${pageCount + 1}: ${extractError.message}`);
      
      // If browser is closed, break out of the loop
      if (extractError.message.includes('closed') || extractError.message.includes('Target page')) {
        console.error('Browser context closed during extraction.');
        break;
      }
      
      break;
    }
  }

  console.log(`Total events extracted from ${sectionName}: ${sectionEvents.length}`);
  return sectionEvents;
}

/**
 * Main scraper function for Brooklyn Academy of Music
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase (shared utility)
 * 2. Open Browserbase session URL in browser (shared utility)
 * 3. Navigate to BAM homepage
 * 4. Iterate through sections: Music, Theater, Dance, Talks, Opera, Poetry, Kids, Performance Art, Holiday
 * 5. For each section: extract events and paginate via right arrow
 * 6. Expand date ranges into individual events
 * 7. Log results (shared utility)
 * 8. Save to database and run tests (shared utility)
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapeBAM() {
  // Initialize Stagehand using shared utility function
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open Browserbase session URL in default browser using shared utility
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to BAM homepage
    await page.goto("https://www.bam.org/");
    // BAM has continuous network activity, so use timeout instead of networkidle
    await page.waitForTimeout(5000);
    
    // Step 2: Scroll down to load content
    await page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight);
    });
    await page.waitForTimeout(2000);
    
    // Step 3: Extract events from each section
    const sections = [
      'Music',
      'Theater',
      'Dance',
      'Talks',
      'Opera',
      'Poetry',
      'Kids',
      'Performance Art',
      'Holiday'
    ];
    
    const allEvents = [];
    
    for (const section of sections) {
      try {
        console.log(`\n=== Processing ${section} section ===`);
        
        // Scroll to the section
        await page.act(`scroll down to the ${section} section`);
        await page.waitForTimeout(1000);
        
        // Extract events from this section ONLY (not all visible events)
        const sectionEvents = await extractEventsFromSection(page, section);
        allEvents.push(...sectionEvents);
        
        console.log(`Completed ${section}: ${sectionEvents.length} events`);
      } catch (sectionError) {
        console.error(`Error processing ${section} section: ${sectionError.message}`);
        
        // If browser is closed, we can't continue with other sections
        if (sectionError.message.includes('closed') || sectionError.message.includes('Target page')) {
          console.error('Browser context closed. Stopping section processing.');
          break;
        }
        
        // Continue with next section for other errors
      }
    }
    
    console.log(`\nSuccessfully extracted ${allEvents.length} total events across all sections`);
    
    // Step 4: Expand date ranges into individual events
    console.log("\n=== Expanding date ranges into individual events ===");
    const expandedEvents = [];
    
    for (const event of allEvents) {
      const dates = expandDateRange(event.eventDate);
      
      for (const date of dates) {
        expandedEvents.push({
          ...event,
          eventDate: date
        });
      }
    }
    
    console.log(`Expanded ${allEvents.length} events into ${expandedEvents.length} individual events`);
    
    // Step 5: Deduplicate events (same event+date combination may appear in multiple sections)
    console.log("\n=== Deduplicating events ===");
    const uniqueEventsMap = new Map();
    for (const event of expandedEvents) {
      const key = `${event.eventName}|${event.eventDate}`;
      if (!uniqueEventsMap.has(key)) {
        uniqueEventsMap.set(key, event);
      }
    }
    const deduplicatedEvents = Array.from(uniqueEventsMap.values());
    console.log(`Deduplicated ${expandedEvents.length} events into ${deduplicatedEvents.length} unique events`);
    
    // Backup: Add hardcoded venue name to all events
    const eventsWithDefaults = deduplicatedEvents.map(event => ({
      ...event,
      eventLocation: "Brooklyn Academy of Music"
    }));

    // Log scraping results using shared utility function
    logScrapingResults(eventsWithDefaults, 'Brooklyn Academy of Music');
    
    // Save to database and run tests using shared utility function
    if (eventsWithDefaults.length > 0) {
      await saveEventsToDatabase(eventsWithDefaults, 'bam');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithDefaults };

  } catch (error) {
    // Handle errors using shared utility function
    await handleScraperError(error, page, 'Brooklyn Academy of Music');
  } finally {
    // Always close Stagehand session to clean up browser resources
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeBAM().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeBAM;

