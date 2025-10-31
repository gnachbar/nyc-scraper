/**
 * Shapeshifter Plus Scraper
 * 
 * Scrapes event listings from Shapeshifter Plus
 * URL: https://shapeshifterplus.org/events/list/
 * 
 * Key Features:
 * - Single-venue scraper (hardcodes 'Shapeshifter Plus' as eventLocation)
 * - Pagination via right arrow button (next to "Today")
 * - Uses shared utility functions from src/lib/
 */

// Import shared utilities from src/lib/
import { initStagehand, openBrowserbaseSession, createStandardSchema } from '../lib/scraper-utils.js';
import { extractEventsFromPage, extractEventTimesFromPages } from '../lib/scraper-actions.js';
import { logScrapingResults, saveEventsToDatabase, handleScraperError } from '../lib/scraper-persistence.js';
import { z } from 'zod';

/**
 * Create standardized event schema with venue default for single-venue scraper
 * The schema will automatically set eventLocation to 'Shapeshifter Plus' for all events
 */
const StandardEventSchema = createStandardSchema({ eventLocationDefault: 'Shapeshifter Plus' });

// Lenient schema used only for initial extraction to avoid strict URL validation failures
const LenientEventSchema = z.object({
  events: z.array(z.object({
    eventName: z.string(),
    eventDate: z.string(),
    eventTime: z.string().default(""),
    eventLocation: z.string().default('Shapeshifter Plus'),
    eventUrl: z.string() // allow any string initially; will be normalized later
  }))
});

/**
 * Main scraper function for Shapeshifter Plus
 * 
 * Flow:
 * 1. Initialize Stagehand with Browserbase
 * 2. Open Browserbase session URL in browser
 * 3. Navigate to Shapeshifter Plus events list page
 * 4. Extract events from first page
 * 5. Click right arrow button (next to "Today") to navigate to next page
 * 6. Extract events from each subsequent page
 * 7. Continue until right arrow is no longer clickable
 * 8. Log results and save to database
 * 
 * @returns {Promise<Object>} Object containing events array
 */
export async function scrapeShapeshifterPlus() {
  const stagehand = await initStagehand({ env: 'BROWSERBASE' });
  const page = stagehand.page;

  try {
    // Open the Browserbase session URL in default browser
    console.log(`Stagehand Session Started`);
    console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
    openBrowserbaseSession(stagehand.browserbaseSessionID);

    // Step 1: Navigate to the events list page
    await page.goto("https://shapeshifterplus.org/events/list/");
    // Try networkidle, but fallback to timeout if it exceeds 30 seconds (some sites have continuous network activity)
    try {
      await page.waitForLoadState('networkidle', { timeout: 30000 });
    } catch (error) {
      console.log("networkidle timed out, using timeout fallback...");
      await page.waitForTimeout(5000); // Wait 5 seconds for initial load
    }
    
    // Array to collect all events from all pages
    const allEvents = [];
    let pageCount = 0;
    const maxPages = 50; // Safety limit to prevent infinite loops
    
    // Step 2-4: Loop through pages
    while (pageCount < maxPages) {
      pageCount++;
      console.log(`Extracting events from page ${pageCount}...`);
      
      // Extract events from current page
      const result = await extractEventsFromPage(
        page,
        "Extract all visible events from the page. For each event: 1) get the event title text (as eventName); 2) get the event date (as eventDate, include the full year, e.g., 'Thursday, October 30, 2025'); 3) get the event time if available (as eventTime, e.g., '7:00 pm') — if no time is present, return an empty string for eventTime; 4) set eventLocation to 'Shapeshifter Plus' for all events; 5) click or inspect the LINK on the EVENT NAME/TITLE and return the anchor href to the event details page (as eventUrl). Returning a relative URL is acceptable. Do not return IDs like '0-459'; return the actual href from the event title link.",
        LenientEventSchema,
        { sourceName: 'shapeshifter_plus' }
      );
      
      // DOM-based extraction of event title anchors and hrefs (more reliable)
      const linkItems = await page.evaluate(() => {
        const anchors = Array.from(document.querySelectorAll('a[href*="/event/"]'));
        return anchors.map(a => ({
          title: (a.textContent || '').trim(),
          href: a.getAttribute('href') || ''
        }));
      });

      const normalizeTitle = (t) => t
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .replace(/[\u201C\u201D\u2019]/g, '"')
        .replace(/[^a-z0-9\s\-:&()]/g, '')
        .trim();

      const titleToHref = new Map();
      for (const item of (linkItems || [])) {
        if (item && item.title) {
          titleToHref.set(normalizeTitle(item.title), item.href || "");
        }
      }

      // Merge URLs from title hrefs into events
      const mergedEvents = result.events.map(ev => {
        const norm = normalizeTitle(ev.eventName || "");
        let directHref = titleToHref.get(norm);
        if (!directHref) {
          // Fallback: try loose match
          for (const [k, v] of titleToHref.entries()) {
            if (k.includes(norm) || norm.includes(k)) {
              directHref = v;
              break;
            }
          }
        }
        return {
          ...ev,
          eventUrl: directHref || ev.eventUrl || ""
        };
      });

      // Normalize URLs to absolute and enforce /event/ prefix
      const normalized = mergedEvents.map(ev => {
        let href = ev.eventUrl || "";
        if (href && !href.startsWith('http')) {
          if (href.startsWith('/')) {
            href = `https://shapeshifterplus.org${href}`;
          } else {
            href = `https://shapeshifterplus.org/event/${href.replace(/^\/+/, '')}`;
          }
        }
        // Ensure it points to an event page
        if (!href.startsWith('https://shapeshifterplus.org/event/')) {
          href = '';
        }
        return { ...ev, eventUrl: href };
      }).filter(ev => ev.eventUrl);

      // Add events to collection (time extraction deferred until after pagination)
      allEvents.push(...normalized);
      console.log(`Found ${result.events.length} events on page ${pageCount}`);
      console.log(`Total events so far: ${allEvents.length}`);
      
      // Step 3: Click the right arrow button (next to "Today") with retries
      let advanced = false;
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          console.log(`Looking for right arrow button (attempt ${attempt}/3)...`);
          const [arrowAction] = await page.observe("click the right arrow button that is on the top left of the page next to 'Today'");
          if (!arrowAction) {
            console.log("Right arrow button not found.");
            await page.waitForTimeout(800 * attempt);
            continue;
          }
          await page.act(arrowAction);
          console.log(`Clicked right arrow, moving to page ${pageCount + 1} (attempt ${attempt})...`);
          try {
            await page.waitForLoadState('networkidle', { timeout: 30000 });
          } catch {
            console.log("networkidle timed out after pagination, using timeout fallback...");
            await page.waitForTimeout(3000 + 500 * attempt);
          }
          await page.waitForTimeout(1500);
          advanced = true;
          break;
        } catch (clickErr) {
          console.log(`Pagination click failed (attempt ${attempt}/3): ${clickErr.message}`);
          // small backoff then retry
          try { await page.waitForTimeout(800 * attempt); } catch {}
        }
      }
      if (!advanced) {
        console.log("No further pagination possible. All pages processed.");
        break;
      }
    }
    
    console.log(`Completed pagination: ${pageCount} page(s) processed, ${allEvents.length} total events found`);

    // After pagination, normalize times for special cases and then fill missing times by visiting detail pages (single pass)
    let eventsPostPagination = allEvents.map(e => {
      const name = (e.eventName || '').trim().toLowerCase();
      if (name.startsWith('protected:')) {
        return { ...e, eventTime: "7:00 pm" };
      }
      return e;
    });

    // Only attempt time extraction for non-"Protected:" events still missing time
    const missingTimeAfter = eventsPostPagination.filter(e => {
      const name = (e.eventName || '').trim().toLowerCase();
      const isProtected = name.startsWith('protected:');
      return !isProtected && (!e.eventTime || e.eventTime.trim() === "");
    });
    if (missingTimeAfter.length > 0) {
      console.log(`Attempting time extraction for ${missingTimeAfter.length} events without times after pagination...`);
      eventsPostPagination = await extractEventTimesFromPages(stagehand, eventsPostPagination, { timeout: 30000, delay: 250 });
    }
    
    // Add hardcoded venue name to all events (backup in case schema default fails)
    const eventsWithLocation = eventsPostPagination.map(event => {
      let eventUrl = event.eventUrl || "";
      if (eventUrl && !eventUrl.startsWith('http')) {
        // Normalize relative or partial URLs to absolute
        if (eventUrl.startsWith('/')) {
          eventUrl = `https://shapeshifterplus.org${eventUrl}`;
        } else {
          eventUrl = `https://shapeshifterplus.org/event/${eventUrl.replace(/^\/+/, '')}`;
        }
      }
      return {
        ...event,
        eventUrl,
        eventLocation: "Shapeshifter Plus"
      };
    });

    // Log scraping results
    logScrapingResults(eventsWithLocation, 'Shapeshifter Plus');
    
    // Save to database and run tests
    if (eventsWithLocation.length > 0) {
      await saveEventsToDatabase(eventsWithLocation, 'shapeshifter_plus');
    } else {
      console.log("No events found!");
    }

    return { events: eventsWithLocation };

  } catch (error) {
    await handleScraperError(error, page, 'Shapeshifter Plus');
  } finally {
    await stagehand.close();
  }
}

// Run the scraper if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  scrapeShapeshifterPlus().catch(err => {
    console.error(err);
    process.exit(1);
  });
}

// Export the function for use in other modules
export default scrapeShapeshifterPlus;

