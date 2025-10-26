import { Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod";
import { exec } from "child_process";

/**
 * Initialize Stagehand with Browserbase
 * @param {Object} options - Configuration options
 * @param {string} [options.env='BROWSERBASE'] - Environment to use
 * @param {number} [options.verbose=1] - Verbosity level (default: 1)
 * @returns {Promise<Object>} Initialized Stagehand instance
 */
export async function initStagehand(options = {}) {
  const { env = 'BROWSERBASE', verbose } = options;
  
  const stagehand = new Stagehand({
    env,
    verbose: verbose ?? 1, // Default to 1 if not specified
  });

  await stagehand.init();
  
  return stagehand;
}

/**
 * Open Browserbase session URL in the default browser
 * @param {string} sessionId - Browserbase session ID
 */
export function openBrowserbaseSession(sessionId) {
  const openCommand = process.platform === 'darwin' ? 'open' : 
                     process.platform === 'win32' ? 'start' : 'xdg-open';
  
  exec(`${openCommand} https://browserbase.com/sessions/${sessionId}`, (error) => {
    if (error) {
      console.log('Could not automatically open browser. Please manually open the URL above.');
    } else {
      console.log('Opened Browserbase session in your default browser');
    }
  });
}

/**
 * Create standardized event schema for all scrapers
 * @param {Object} options - Schema configuration options
 * @param {string} [options.eventLocationDefault] - Default value for eventLocation field
 * @returns {z.ZodObject} StandardEventSchema with configured options
 */
export function createStandardSchema(options = {}) {
  const { eventLocationDefault } = options;
  
  const eventSchema = {
    eventName: z.string(),
    eventDate: z.string(),
    eventTime: z.string().default(""), // Required field, empty string if not found
    eventUrl: z.string().url()
  };
  
  // Add eventLocation with optional default value
  if (eventLocationDefault) {
    eventSchema.eventLocation = z.string().default(eventLocationDefault);
  } else {
    eventSchema.eventLocation = z.string();
  }
  
  return z.object({
    events: z.array(z.object(eventSchema))
  });
}

/**
 * Scroll page to bottom and wait for content to load
 * @param {Object} page - Stagehand page object
 * @param {number} [waitTime] - Time to wait after scrolling in milliseconds (default: 2000ms, minimum enforced)
 */
export async function scrollToBottom(page, waitTime) {
  const DEFAULT_WAIT_TIME = 2000;
  const MIN_WAIT_TIME = 2000;
  
  // Use provided waitTime if it's >= minimum, otherwise use minimum
  const actualWaitTime = waitTime && waitTime >= MIN_WAIT_TIME ? waitTime : MIN_WAIT_TIME;
  
  await page.evaluate(() => {
    window.scrollTo(0, document.body.scrollHeight);
  });
  await page.waitForTimeout(actualWaitTime);
}

