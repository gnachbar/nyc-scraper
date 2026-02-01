/**
 * Browserbase Session Diagnostics
 *
 * Retrieves and analyzes session logs from Browserbase to understand
 * what happened during a scraper run. This provides crucial feedback
 * for the self-healing loop.
 */

import 'dotenv/config';
import Browserbase from '@browserbasehq/sdk';

// Lazily initialize Browserbase SDK
let bb = null;

function getBrowserbaseClient() {
  if (!bb) {
    const apiKey = process.env.BROWSERBASE_API_KEY;
    if (!apiKey) {
      console.warn('[BB-DIAG] BROWSERBASE_API_KEY not set - session diagnostics disabled');
      return null;
    }
    bb = new Browserbase({ apiKey });
  }
  return bb;
}

/**
 * Retrieve session logs for a given session ID
 * @param {string} sessionId - Browserbase session ID
 * @returns {Promise<Array>} Session logs
 */
export async function getSessionLogs(sessionId) {
  const client = getBrowserbaseClient();
  if (!client) {
    return [];
  }

  try {
    const logs = await client.sessions.logs.list(sessionId);
    return logs;
  } catch (error) {
    console.error(`Failed to retrieve session logs: ${error.message}`);
    return [];
  }
}

/**
 * Analyze session logs to understand what happened
 * @param {Array} logs - Session logs from Browserbase
 * @returns {Object} Analysis of the session
 */
export function analyzeSessionLogs(logs) {
  const analysis = {
    totalEvents: logs.length,
    navigations: [],
    clicks: [],
    scrollEvents: [],
    errors: [],
    networkRequests: [],
    pageEvaluations: [],
    timeline: [],
    summary: {
      hasScrolled: false,
      scrollCount: 0,
      clickCount: 0,
      errorCount: 0,
      pageLoadCount: 0,
      lastEventTime: null,
      sessionDuration: 0,
    }
  };

  if (logs.length === 0) {
    return analysis;
  }

  let firstTimestamp = null;
  let lastTimestamp = null;

  for (const log of logs) {
    const method = log.method || '';
    const timestamp = log.timestamp;

    if (firstTimestamp === null) firstTimestamp = timestamp;
    lastTimestamp = timestamp;

    // Track navigations
    if (method.includes('Page.navigate') || method.includes('Page.frameNavigated')) {
      const url = log.request?.params?.url || log.response?.result?.url || 'unknown';
      analysis.navigations.push({
        timestamp,
        url,
        method
      });
      analysis.summary.pageLoadCount++;
    }

    // Track scroll events
    if (method.includes('Input.dispatchMouseEvent') || method.includes('Input.synthesizeScrollGesture')) {
      const params = log.request?.params || {};
      if (params.type === 'mouseWheel' || method.includes('Scroll')) {
        analysis.scrollEvents.push({
          timestamp,
          params
        });
        analysis.summary.hasScrolled = true;
        analysis.summary.scrollCount++;
      }
    }

    // Track clicks
    if (method.includes('Input.dispatchMouseEvent')) {
      const params = log.request?.params || {};
      if (params.type === 'mousePressed' || params.type === 'mouseReleased') {
        analysis.clicks.push({
          timestamp,
          x: params.x,
          y: params.y,
          button: params.button
        });
        analysis.summary.clickCount++;
      }
    }

    // Track page evaluations (JavaScript execution)
    if (method.includes('Runtime.evaluate') || method.includes('Runtime.callFunctionOn')) {
      const expression = log.request?.params?.expression || log.request?.params?.functionDeclaration || '';

      // Check if it's a scroll-related evaluation
      if (expression.includes('scroll') || expression.includes('Scroll')) {
        analysis.scrollEvents.push({
          timestamp,
          type: 'js_scroll',
          expression: expression.substring(0, 200)
        });
        analysis.summary.hasScrolled = true;
        analysis.summary.scrollCount++;
      }

      analysis.pageEvaluations.push({
        timestamp,
        expression: expression.substring(0, 100) + (expression.length > 100 ? '...' : '')
      });
    }

    // Track errors
    if (log.response?.result?.exceptionDetails || method.includes('Error')) {
      analysis.errors.push({
        timestamp,
        method,
        error: log.response?.result?.exceptionDetails || log.response?.result
      });
      analysis.summary.errorCount++;
    }

    // Build timeline
    analysis.timeline.push({
      timestamp,
      method,
      summary: summarizeLogEntry(log)
    });
  }

  // Calculate session duration
  if (firstTimestamp && lastTimestamp) {
    analysis.summary.sessionDuration = (lastTimestamp - firstTimestamp) / 1000; // seconds
    analysis.summary.lastEventTime = new Date(lastTimestamp).toISOString();
  }

  return analysis;
}

/**
 * Summarize a single log entry
 */
function summarizeLogEntry(log) {
  const method = log.method || 'unknown';
  const params = log.request?.params || {};

  if (method.includes('navigate')) {
    return `Navigate to: ${params.url || 'unknown'}`;
  }
  if (method.includes('evaluate')) {
    const expr = params.expression || params.functionDeclaration || '';
    if (expr.includes('scroll')) return 'JavaScript scroll';
    if (expr.includes('click')) return 'JavaScript click';
    return 'JavaScript evaluation';
  }
  if (method.includes('MouseEvent')) {
    return `Mouse ${params.type} at (${params.x}, ${params.y})`;
  }

  return method;
}

/**
 * Generate a diagnostic report from session logs
 * @param {string} sessionId - Browserbase session ID
 * @returns {Promise<Object>} Diagnostic report
 */
export async function generateSessionDiagnostics(sessionId) {
  console.log(`[BB-DIAG] Fetching logs for session: ${sessionId}`);

  const logs = await getSessionLogs(sessionId);
  const analysis = analyzeSessionLogs(logs);

  console.log(`[BB-DIAG] Session Analysis:`);
  console.log(`   Total events: ${analysis.totalEvents}`);
  console.log(`   Navigations: ${analysis.navigations.length}`);
  console.log(`   Scrolled: ${analysis.summary.hasScrolled} (${analysis.summary.scrollCount} times)`);
  console.log(`   Clicks: ${analysis.summary.clickCount}`);
  console.log(`   Errors: ${analysis.summary.errorCount}`);
  console.log(`   Duration: ${analysis.summary.sessionDuration}s`);

  // Generate insights
  const insights = [];

  if (!analysis.summary.hasScrolled) {
    insights.push({
      type: 'warning',
      message: 'NO SCROLL EVENTS DETECTED - page may not have scrolled to load content'
    });
  }

  if (analysis.summary.scrollCount < 3 && analysis.navigations.length > 0) {
    insights.push({
      type: 'warning',
      message: `Only ${analysis.summary.scrollCount} scroll events - may not have scrolled enough to load all content`
    });
  }

  if (analysis.summary.errorCount > 0) {
    insights.push({
      type: 'error',
      message: `${analysis.summary.errorCount} errors detected during session`,
      errors: analysis.errors
    });
  }

  if (analysis.summary.sessionDuration < 5) {
    insights.push({
      type: 'warning',
      message: `Session only lasted ${analysis.summary.sessionDuration}s - may have crashed early`
    });
  }

  return {
    sessionId,
    analysis,
    insights,
    recommendations: generateRecommendations(analysis, insights)
  };
}

/**
 * Generate recommendations based on analysis
 */
function generateRecommendations(analysis, insights) {
  const recommendations = [];

  const hasScrollWarning = insights.some(i => i.message.includes('SCROLL') || i.message.includes('scroll'));
  const hasErrors = analysis.summary.errorCount > 0;
  const shortSession = analysis.summary.sessionDuration < 10;

  if (hasScrollWarning) {
    recommendations.push({
      priority: 1,
      action: 'verify_scroll_implementation',
      description: 'Verify scrollToBottom is being called and actually scrolling the page',
      code_hint: [
        '// Add explicit scroll verification',
        'const initialHeight = await page.evaluate(() => document.body.scrollHeight);',
        'await scrollToBottom(page);',
        'const finalHeight = await page.evaluate(() => document.body.scrollHeight);',
        'console.log(`Scroll result: ${initialHeight} -> ${finalHeight}`);'
      ].join('\n')
    });
  }

  if (shortSession && hasErrors) {
    recommendations.push({
      priority: 1,
      action: 'add_error_recovery',
      description: 'Session crashed early - add try-catch and recovery around key operations'
    });
  }

  if (analysis.summary.clickCount > 0 && analysis.summary.clickCount < 3) {
    recommendations.push({
      priority: 2,
      action: 'investigate_click_failure',
      description: `Only ${analysis.summary.clickCount} clicks registered - clicks may be failing silently`
    });
  }

  return recommendations;
}

/**
 * Quick check if a session had scroll issues
 * @param {string} sessionId - Browserbase session ID
 * @returns {Promise<boolean>} True if scroll issues detected
 */
export async function hasScrollIssues(sessionId) {
  const diagnostics = await generateSessionDiagnostics(sessionId);
  return diagnostics.insights.some(i =>
    i.message.includes('SCROLL') || i.message.includes('scroll')
  );
}

// CLI interface
if (import.meta.url === `file://${process.argv[1]}`) {
  const sessionId = process.argv[2];

  if (!sessionId) {
    console.log('Usage: node src/lib/browserbase-diagnostics.js <session_id>');
    console.log('');
    console.log('Analyzes a Browserbase session to identify issues.');
    process.exit(1);
  }

  generateSessionDiagnostics(sessionId)
    .then(diagnostics => {
      console.log('\n=== FULL DIAGNOSTICS ===');
      console.log(JSON.stringify(diagnostics, null, 2));
    })
    .catch(err => {
      console.error('Error:', err.message);
      process.exit(1);
    });
}
