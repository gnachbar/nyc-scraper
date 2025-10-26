import { Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod";

/**
 * Initialize Stagehand with Browserbase
 * @param {Object} options - Configuration options
 * @param {string} [options.env='BROWSERBASE'] - Environment to use
 * @param {number} [options.verbose=1] - Verbosity level
 * @returns {Promise<Object>} Initialized Stagehand instance
 */
export async function initStagehand(options = {}) {
  const { env = 'BROWSERBASE', verbose = 1 } = options;
  
  const stagehand = new Stagehand({
    env,
    verbose,
  });

  await stagehand.init();
  
  return stagehand;
}

/**
 * Open Browserbase session URL in the default browser
 * @param {string} sessionId - Browserbase session ID
 */
export function openBrowserbaseSession(sessionId) {
  const { exec } = require('child_process');
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
 * @param {number} [waitTime=2000] - Time to wait after scrolling in milliseconds
 */
export async function scrollToBottom(page, waitTime = 2000) {
  await page.evaluate(() => {
    window.scrollTo(0, document.body.scrollHeight);
  });
  await page.waitForTimeout(waitTime);
}

