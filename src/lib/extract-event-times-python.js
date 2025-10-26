import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Extract event times from individual event pages using Python BeautifulSoup
 * This is a more reliable method than Stagehand for certain websites that embed
 * time data in JSON-LD or other structured data.
 * 
 * @param {Array} events - Array of events with eventUrl properties
 * @param {Object} options - Additional options
 * @param {number} [options.workers=10] - Number of parallel workers
 * @param {number} [options.rateLimit=1.0] - Requests per second
 * @returns {Promise<Array>} Updated events array with eventTime populated
 */
export async function extractEventTimesWithPython(events, options = {}) {
  const { workers = 10, rateLimit = 1.0 } = options;
  
  console.log(`Extracting event times using Python for ${events.length} events...`);
  
  // Create a temporary input file
  const tempInputFile = path.join(process.cwd(), `temp_events_input_${Date.now()}.json`);
  const tempOutputFile = path.join(process.cwd(), `temp_events_output_${Date.now()}.json`);
  
  try {
    // Write events to temporary input file
    fs.writeFileSync(tempInputFile, JSON.stringify(events, null, 2));
    console.log(`Wrote ${events.length} events to temporary file: ${tempInputFile}`);
    
    // Call the Python script
    const pythonScript = path.join(__dirname, '..', 'extract_event_times.py');
    const cmd = [
      'python3',
      pythonScript,
      tempInputFile,
      tempOutputFile,
      '--workers', workers.toString(),
      '--rate-limit', rateLimit.toString()
    ].join(' ');
    
    console.log(`Running: ${cmd}`);
    
    const output = execSync(cmd, { 
      encoding: 'utf-8',
      maxBuffer: 10 * 1024 * 1024 // 10MB buffer
    });
    
    console.log(output);
    
    // Read the enriched events from the output file
    const enrichedEventsContent = fs.readFileSync(tempOutputFile, 'utf-8');
    const enrichedEvents = JSON.parse(enrichedEventsContent);
    
    console.log(`Successfully extracted times for ${enrichedEvents.length} events`);
    
    // Count how many events got times
    const eventsWithTimes = enrichedEvents.filter(e => e.eventTime && e.eventTime !== '').length;
    console.log(`Events with times: ${eventsWithTimes}/${enrichedEvents.length}`);
    
    return enrichedEvents;
    
  } catch (error) {
    console.error('Error extracting times with Python:', error.message);
    console.error('Returning original events without times');
    return events;
  } finally {
    // Clean up temporary files
    try {
      if (fs.existsSync(tempInputFile)) {
        fs.unlinkSync(tempInputFile);
      }
      if (fs.existsSync(tempOutputFile)) {
        fs.unlinkSync(tempOutputFile);
      }
    } catch (cleanupError) {
      console.warn('Failed to clean up temporary files:', cleanupError.message);
    }
  }
}

