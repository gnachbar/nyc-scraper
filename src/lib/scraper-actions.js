import { z } from "zod";

/**
 * Click a button repeatedly until it's no longer present on the page
 * @param {Object} page - Stagehand page object
 * @param {string} buttonText - Text or description of button to click
 * @param {number} maxClicks - Maximum number of clicks to attempt
 * @param {Object} options - Additional options
 * @param {boolean} [options.scrollAfterClick=true] - Whether to scroll to bottom after each click
 * @param {number} [options.scrollWaitTime=2000] - Time to wait after scrolling
 * @param {number} [options.loadWaitTime=2000] - Time to wait for content to load after click
 * @returns {Promise<number>} Number of successful clicks
 */
export async function clickButtonUntilGone(page, buttonText, maxClicks, options = {}) {
  const { 
    scrollAfterClick = true, 
    scrollWaitTime = 2000, 
    loadWaitTime = 2000 
  } = options;
  
  let clickCount = 0;

  for (let i = 0; i < maxClicks; i++) {
    try {
      console.log(`Attempting to click "${buttonText}" (attempt ${i + 1}/${maxClicks})`);
      
      const [buttonAction] = await page.observe(`click the '${buttonText}' button`);
      
      if (buttonAction) {
        await page.act(buttonAction);
        clickCount++;
        console.log(`Successfully clicked "${buttonText}" (${clickCount}/${maxClicks})`);
        
        // Wait for new content to load
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(loadWaitTime);
        
        // Scroll to bottom if requested
        if (scrollAfterClick) {
          await page.evaluate(() => {
            window.scrollTo(0, document.body.scrollHeight);
          });
          await page.waitForTimeout(scrollWaitTime);
        }
      } else {
        console.log(`No "${buttonText}" button found. All content may be loaded.`);
        break;
      }
    } catch (error) {
      console.log(`Failed to click "${buttonText}" on attempt ${i + 1}: ${error.message}`);
      break;
    }
  }

  console.log(`Total "${buttonText}" clicks: ${clickCount}`);
  return clickCount;
}

/**
 * Extract events from page with error handling
 * @param {Object} page - Stagehand page object
 * @param {string} instruction - Extraction instruction for Stagehand
 * @param {z.ZodObject} schema - Zod schema for validation
 * @param {Object} options - Additional options
 * @param {string} [options.sourceName] - Source name for screenshot naming
 * @returns {Promise<Object>} Extraction result with events array
 */
export async function extractEventsFromPage(page, instruction, schema, options = {}) {
  const { sourceName = 'unknown' } = options;
  
  try {
    const result = await page.extract({
      instruction,
      schema
    });
    
    return result;
  } catch (extractError) {
    console.error("Extraction failed:", extractError.message);
    console.log("Taking screenshot for debugging...");
    await page.screenshot({ path: `${sourceName}_extraction_failed.png` });
    throw new Error(`Failed to extract events: ${extractError.message}`);
  }
}

/**
 * Validate extraction result
 * @param {Object} result - Extraction result object
 * @param {Object} options - Additional options
 * @param {string} [options.sourceName] - Source name for screenshot naming
 * @returns {Object} Validation object with isValid boolean and error message if invalid
 */
export function validateExtractionResult(result, options = {}) {
  const { sourceName = 'unknown' } = options;
  
  if (!result || !result.events) {
    return {
      isValid: false,
      error: "Extraction returned no events"
    };
  }
  
  return {
    isValid: true,
    error: null
  };
}

/**
 * Extract event times from individual event pages (for Kings Theatre scraper)
 * @param {Object} stagehand - Stagehand instance
 * @param {Array} events - Array of events with eventUrl properties
 * @param {Object} options - Additional options
 * @param {number} [options.timeout=30000] - Timeout for page navigation
 * @param {number} [options.delay=500] - Delay between page extractions
 * @returns {Promise<Array>} Updated events array with eventTime populated
 */
export async function extractEventTimesFromPages(stagehand, events, options = {}) {
  const { timeout = 30000, delay = 500 } = options;
  
  console.log(`Extracting event times from ${events.length} individual event pages...`);
  
  for (let i = 0; i < events.length; i++) {
    const event = events[i];
    console.log(`Processing event ${i + 1}/${events.length}: ${event.eventName}`);
    
    let eventPage = null;
    try {
      // Create a new page for this event
      eventPage = await stagehand.context.newPage();
      
      // Navigate to the event page with timeout
      await eventPage.goto(event.eventUrl, { timeout });
      await eventPage.waitForLoadState('networkidle', { timeout });
      
      // Extract time information from the event page
      const timeResult = await eventPage.extract({
        instruction: "Extract the event time/start time from this event page. Look for time information like '8:00 PM', '7:30 PM', 'Doors: 7:00 PM', 'Show: 8:00 PM', etc. Return just the time string if found, or an empty string if no time is available.",
        schema: z.object({
          eventTime: z.string().default("")
        })
      });
      
      // Update the event with the extracted time
      events[i] = {
        ...event,
        eventTime: timeResult.eventTime || ""
      };
      
      console.log(`  Time extracted: ${timeResult.eventTime || 'No time found'}`);
      
      // Small delay to be respectful to the server
      await eventPage.waitForTimeout(delay);
      
    } catch (error) {
      console.warn(`  Failed to extract time for ${event.eventName}: ${error.message}`);
      // Continue with other events even if one fails
    } finally {
      // Always close the event page if it was created
      if (eventPage) {
        try {
          await eventPage.close();
        } catch (closeError) {
          console.warn(`  Failed to close page for ${event.eventName}: ${closeError.message}`);
        }
      }
    }
    
    // Check if we should continue (browser context still active)
    try {
      await stagehand.page.waitForTimeout(100); // Small check to see if context is still alive
    } catch (contextError) {
      console.warn(`Browser context closed after ${i + 1} events. Stopping time extraction.`);
      break;
    }
  }
  
  return events;
}

/**
 * Paginate through pages extracting events (for Prospect Park scraper)
 * @param {Object} page - Stagehand page object
 * @param {Function} extractFn - Function to extract events from current page
 * @param {number} maxPages - Maximum number of pages to process
 * @param {Object} options - Additional options
 * @param {string} [options.nextButtonText="Next events"] - Text of the next button
 * @param {number} [options.pageWaitTime=3000] - Time to wait after clicking next
 * @returns {Promise<Array>} Array of all extracted events
 */
export async function paginateThroughPages(page, extractFn, maxPages, options = {}) {
  const { nextButtonText = "Next events", pageWaitTime = 3000 } = options;
  
  const allEvents = [];
  let pageCount = 0;

  while (pageCount < maxPages) {
    console.log(`Extracting events from page ${pageCount + 1}/${maxPages}...`);
    
    const result = await extractFn();
    allEvents.push(...result.events);
    console.log(`Found ${result.events.length} events on page ${pageCount + 1}`);

    // Try to click next button
    try {
      const [nextAction] = await page.observe(`click the '${nextButtonText}' button`);
      
      if (nextAction) {
        await page.act(nextAction);
        pageCount++;
        console.log(`Successfully clicked '${nextButtonText}' button (${pageCount}/${maxPages})`);
        
        // Wait for new content to load
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(pageWaitTime);
      } else {
        console.log(`No more '${nextButtonText}' button found. All pages processed.`);
        break;
      }
    } catch (error) {
      console.log(`Failed to click '${nextButtonText}' button: ${error.message}`);
      console.log("Continuing to extract from current page...");
      // Don't break, continue to extract from current page
    }
  }

  console.log(`Total pages processed: ${pageCount}`);
  console.log(`Total events found: ${allEvents.length}`);
  
  return allEvents;
}

