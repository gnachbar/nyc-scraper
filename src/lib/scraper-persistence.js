import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

// Helper to get Python command - prefer venv if available
function getPythonCommand() {
  const venvPython = path.join(process.cwd(), 'venv', 'bin', 'python');
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  return 'python3';
}

/**
 * Log scraping results with time validation
 * @param {Array} events - Array of extracted events
 * @param {string} sourceName - Name of the source being scraped
 * @param {Object} options - Additional options
 * @param {number} [options.maxEventsToShow=5] - Number of events to display in summary
 */
export function logScrapingResults(events, sourceName, options = {}) {
  const { maxEventsToShow = 5 } = options;
  
  console.log(`=== ${sourceName.toUpperCase()} Scraping Results ===`);
  console.log(`Total events found: ${events.length}`);
  
  // Count events with and without times
  const eventsWithTimes = events.filter(e => e.eventTime && e.eventTime.trim() !== '').length;
  const eventsWithoutTimes = events.length - eventsWithTimes;
  
  if (eventsWithoutTimes > 0) {
    console.log(`⚠ WARNING: ${eventsWithoutTimes}/${events.length} events missing times`);
  } else {
    console.log(`✓ All ${events.length} events have times`);
  }
  
  if (events.length > 0) {
    console.log("\nFirst few events:");
    events.slice(0, maxEventsToShow).forEach((event, index) => {
      console.log(`${index + 1}. ${event.eventName}`);
      console.log(`   Date: ${event.eventDate}`);
      console.log(`   Time: ${event.eventTime || 'N/A'}`);
      console.log(`   Location: ${event.eventLocation}`);
      console.log(`   URL: ${event.eventUrl}`);
      console.log('');
    });
  } else {
    console.log("No events found!");
  }
}

/**
 * Save events to database and run tests
 * @param {Array} events - Array of events to save
 * @param {string} sourceName - Name of the source
 * @param {Object} options - Additional options
 * @returns {Promise<void>}
 */
export async function saveEventsToDatabase(events, sourceName, options = {}) {
  console.log("Writing events to database...");
  
  // Create temporary JSON file for import
  const tempFile = path.join(process.cwd(), `temp_${sourceName}_${Date.now()}.json`);
  fs.writeFileSync(tempFile, JSON.stringify({ events }, null, 2));
  
  try {
    const pythonCmd = getPythonCommand();
    // Import to database using existing import script
    execSync(`${pythonCmd} src/import_scraped_data.py --source ${sourceName} --file ${tempFile}`, { stdio: 'inherit' });
    console.log(`Successfully imported ${events.length} events to database`);

    // Run scraper test to compare with previous run
    console.log("Running scraper test...");
    try {
      execSync(`${pythonCmd} src/test_scrapers.py --source ${sourceName}`, { stdio: 'inherit' });
      console.log("Scraper test completed successfully");
    } catch (testError) {
      console.warn("Scraper test failed (non-critical):", testError.message);
      // Don't throw - test failure shouldn't stop the scraper
    }
  } catch (importError) {
    console.error("Database import failed:", importError);
    throw importError;
  } finally {
    // Clean up temporary file
    if (fs.existsSync(tempFile)) {
      fs.unlinkSync(tempFile);
    }
  }
}

/**
 * Handle scraper errors with screenshot capture
 * @param {Error} error - The error that occurred
 * @param {Object} page - Stagehand page object
 * @param {string} sourceName - Name of the source
 */
export async function handleScraperError(error, page, sourceName) {
  console.error(`${sourceName} scraping failed:`, error);
  
  // Try to capture screenshot if page is available
  if (page) {
    try {
      await page.screenshot({ path: `${sourceName}_error.png` });
      console.log(`Screenshot saved: ${sourceName}_error.png`);
    } catch (screenshotError) {
      console.warn("Failed to capture error screenshot:", screenshotError.message);
    }
  }
  
  throw error;
}


