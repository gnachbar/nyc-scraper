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
    eventDescription: z.string().default(""), // Event description, empty string if not found
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

/**
 * Convert weekly recurring events to individual dated events
 * @param {Array} weeklyEvents - Array of weekly recurring events with day property
 * @param {Object} options - Configuration options
 * @param {number} [options.monthsAhead=6] - Number of months ahead to generate events (default: 6)
 * @param {string} [options.baseUrl] - Base URL to use for all events (optional)
 * @returns {Array} Array of dated events
 * 
 * @example
 * const weeklyEvents = [
 *   { eventName: "Trivia Night", day: "Tuesday", eventTime: "7:30 PM", ... },
 *   { eventName: "Jazz Night", day: "Wednesday", eventTime: "7:30 PM", ... }
 * ];
 * const datedEvents = convertWeeklyToDatedEvents(weeklyEvents, { monthsAhead: 6 });
 */
/**
 * Normalize event time string to standard format
 * Examples:
 * - "7:30 to 9:30" → "7:30 PM"
 * - "7:30PM" → "7:30 PM"
 * - "starting at 9:00PM" → "9:00 PM"
 * - "10:00AM - 4:00PM" → "10:00 AM"
 */
function normalizeEventTime(timeStr) {
  if (!timeStr || timeStr.trim() === '') {
    return '';
  }
  
  let normalized = timeStr.trim();
  
  // Extract time from phrases like "starting at 9:00PM"
  const startingMatch = normalized.match(/starting\s+at\s+(\d{1,2}:\d{2}(?:AM|PM|am|pm)?)/i);
  if (startingMatch) {
    normalized = startingMatch[1];
  }
  
  // Extract start time from ranges like "7:30 to 9:30" or "10:00AM - 4:00PM"
  if (normalized.includes(' to ') || normalized.includes(' - ') || normalized.includes('–')) {
    const parts = normalized.split(/ to | - |–/);
    if (parts.length > 0) {
      normalized = parts[0].trim();
    }
  }
  
  // Extract just the time portion from strings like "Saturday and Sunday 10:00AM - 4:00PM"
  const timeMatch = normalized.match(/(\d{1,2}:\d{2}(?:AM|PM|am|pm)?)/i);
  if (timeMatch) {
    normalized = timeMatch[1];
  }
  
  // Determine if evening or morning based on context
  // Evening events (after 5pm implied): Trivia, Jazz, Philosophy, DJ, Late Night
  // Morning/Afternoon events: Brunch, Industry Night (all day)
  const isEvening = timeStr.toLowerCase().includes('evening') || 
                    timeStr.toLowerCase().includes('night') ||
                    timeStr.toLowerCase().includes('late');
  
  // Check if already has AM/PM
  const hasAmPm = /(AM|PM|am|pm)/.test(normalized);
  
  if (!hasAmPm) {
    // Add AM/PM based on context or default to PM for evening events
    // Parse the hour
    const hourMatch = normalized.match(/(\d{1,2}):?(\d{2})?/);
    if (hourMatch) {
      const hour = parseInt(hourMatch[1]);
      const minute = hourMatch[2] || '00';
      
      // Business logic for Le Pistol events:
      // - Hours 7-11: typically PM for evening events (trivia, jazz, DJ)
      // - Hour 10+: could be AM for brunch or PM for evening - check context
      // - Default to PM for events with "night" or "late" in description
      if (hour === 10 && timeStr.toLowerCase().includes('am -')) {
        // Brunch event: "10:00AM - 4:00PM"
        normalized = `${hour}:${minute} AM`;
      } else if (hour < 7) {
        // Early morning (6am or earlier)
        normalized = `${hour}:${minute} AM`;
      } else {
        // Default to PM for evening events (7pm-11pm)
        normalized = `${hour}:${minute} PM`;
      }
    }
  } else {
    // Already has AM/PM, just normalize spacing
    normalized = normalized.replace(/(\d{1,2}):(\d{2})(AM|PM|am|pm)/i, '$1:$2 $3');
  }
  
  // Uppercase AM/PM
  normalized = normalized.replace(/\b(am|pm)\b/i, (match) => match.toUpperCase());
  
  return normalized;
}

export function convertWeeklyToDatedEvents(weeklyEvents, options = {}) {
  const { monthsAhead = 6, baseUrl } = options;
  
  const dayMapping = {
    'Monday': 1,
    'Tuesday': 2,
    'Wednesday': 3,
    'Thursday': 4,
    'Friday': 5,
    'Saturday': 6,
    'Sunday': 0
  };
  
  const datedEvents = [];
  const now = new Date();
  const endDate = new Date(now);
  endDate.setMonth(endDate.getMonth() + monthsAhead);
  
  for (const event of weeklyEvents) {
    // Normalize the event time before processing
    const normalizedTime = normalizeEventTime(event.eventTime);
    
    // Handle WEEKENDS special case
    let daysToProcess = [];
    if (event.day === 'WEEKENDS') {
      daysToProcess = ['Saturday', 'Sunday'];
    } else if (dayMapping.hasOwnProperty(event.day)) {
      daysToProcess = [event.day];
    } else {
      console.log(`Skipping event "${event.eventName}" - unrecognized day: ${event.day}`);
      continue;
    }
    
    // Process each day
    for (const day of daysToProcess) {
      const targetDay = dayMapping[day];
      const currentDate = new Date(now);
      
      // Find the next occurrence of this day
      const daysUntilTarget = (targetDay - currentDate.getDay() + 7) % 7;
      if (daysUntilTarget === 0) {
        // If today is the target day, use next week
        currentDate.setDate(currentDate.getDate() + 7);
      } else {
        currentDate.setDate(currentDate.getDate() + daysUntilTarget);
      }
      
      // Generate events for every occurrence until endDate
      while (currentDate <= endDate) {
        const eventDate = new Date(currentDate);
        const formattedDate = eventDate.toLocaleDateString('en-US', { 
          weekday: 'long', 
          year: 'numeric', 
          month: 'long', 
          day: 'numeric' 
        });
        
        datedEvents.push({
          ...event,
          cite: event.cite, // Preserve cite
          eventDate: formattedDate,
          eventTime: normalizedTime, // Use normalized time
          eventUrl: baseUrl || event.eventUrl || ''
        });
        
        // Move to next week
        currentDate.setDate(currentDate.getDate() + 7);
      }
    }
  }
  
  return datedEvents;
}

