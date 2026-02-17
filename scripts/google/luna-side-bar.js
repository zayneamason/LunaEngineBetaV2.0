/**
 * lunaSidebar.gs — Luna Sidebar for Google Sheets
 *
 * Routes all messages through Luna's /message endpoint so users get
 * the full Luna conversational experience — personality, memory,
 * data room awareness — right from the Master Index Sheet.
 *
 * Setup:
 *   1. Set LUNA_API_URL in Script Properties (default: http://localhost:8000)
 *   2. Open the Master Index Sheet
 *   3. Click Data Room > Ask Luna
 */

/**
 * Open the Luna sidebar.
 */
function openLunaSidebar() {
  var html = HtmlService.createHtmlOutputFromFile('lunaSidebar')
    .setTitle('Luna')
    .setWidth(340);
  SpreadsheetApp.getUi().showSidebar(html);
}

/**
 * Check if Luna's API is reachable.
 * Called by the sidebar on load.
 *
 * @return {Object} {connected: boolean, url: string}
 */
function checkLunaStatus() {
  var url = getLunaApiUrl();
  try {
    var response = UrlFetchApp.fetch(url + '/health', {
      muteHttpExceptions: true,
      connectTimeout: 5000,
      headers: { 'Accept': 'application/json' }
    });
    var code = response.getResponseCode();
    if (code === 200) {
      var data = JSON.parse(response.getContentText());
      return {
        connected: true,
        url: url,
        engine: data.status === 'healthy' || data.status === 'ok'
      };
    }
    return { connected: false, url: url, error: 'HTTP ' + code };
  } catch (e) {
    return { connected: false, url: url, error: e.message };
  }
}

/**
 * Send a message to Luna through her full engine pipeline.
 * Uses the /message endpoint for conversational responses,
 * with a data room context hint prepended.
 *
 * @param {string} query - The user's message
 * @return {Object} {success: boolean, response: string}
 */
function askLuna(query) {
  var url = getLunaApiUrl();

  try {
    // Add context hint so Luna knows we're in the data room sidebar
    var contextMessage = query;

    // For the first message or greetings, add sheet context
    var lowerQuery = query.toLowerCase().trim();
    var isGreeting = lowerQuery.match(/^(hey|hi|hello|sup|yo|what'?s up)/);

    if (!isGreeting) {
      // Prepend data room context for non-greetings so Luna's router
      // picks up on data room intent even for casual phrasing
      var hasDataroomIntent = lowerQuery.match(/\b(status|overview|missing|gap|recent|document|file|legal|financial|team|product|category)\b/);
      if (hasDataroomIntent) {
        contextMessage = '[asking from data room sidebar] ' + query;
      }
    }

    var response = UrlFetchApp.fetch(url + '/message', {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify({
        message: contextMessage,
        timeout: 45.0
      }),
      muteHttpExceptions: true,
      headers: { 'Accept': 'application/json' }
    });

    var code = response.getResponseCode();

    if (code === 200) {
      var data = JSON.parse(response.getContentText());
      var text = data.text || data.response || '';

      if (!text) {
        return { success: false, error: 'Luna returned an empty response' };
      }

      return { success: true, response: text };
    }

    if (code === 503) {
      return { success: false, error: 'Luna Engine is starting up — try again in a moment' };
    }

    return { success: false, error: 'API returned ' + code };

  } catch (e) {
    Logger.log('askLuna error: ' + e.message);
    return { success: false, error: 'Cannot reach Luna: ' + e.message };
  }
}

/**
 * Update the Luna API URL in script properties.
 * Called automatically by the local launch script after cloudflared starts.
 *
 * @param {string} newUrl - The new tunnel URL (e.g. https://xyz.trycloudflare.com)
 * @return {Object} {success: boolean, url: string}
 */
function setLunaApiUrl(newUrl) {
  if (!newUrl || typeof newUrl !== 'string') {
    return { success: false, error: 'Invalid URL' };
  }
  var props = PropertiesService.getScriptProperties();
  props.setProperty('LUNA_API_URL', newUrl);
  return { success: true, url: newUrl };
}

/**
 * Get the Luna API URL from script properties.
 * Default: http://localhost:8000
 *
 * @return {string} The Luna API base URL
 */
function getLunaApiUrl() {
  // This line is auto-updated by launch_luna.sh on every tunnel start
  var url = 'https://gerald-andrea-button-robbie.trycloudflare.com';  // AUTO-TUNNEL-URL
  return url;
}
