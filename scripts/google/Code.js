/**
 * setup.gs — Data Room Folder Bootstrapper
 *
 * Creates the full investor data room folder taxonomy in Google Drive
 * and stores all folder IDs in PropertiesService for other scripts.
 *
 * Run once: setupDataRoom()
 */

/**
 * Data room folder structure definition.
 * Order matters — numeric prefixes sort naturally in Drive.
 */
var FOLDER_STRUCTURE = {
  root: '[Project Tapestry] Data Room',
  utility: ['_INBOX', '_INDEX', '_CHANGELOG'],
  categories: [
    '1. Company Overview',
    '2. Financials',
    '3. Legal',
    '4. Product',
    '5. Market & Competition',
    '6. Team',
    '7. Go-to-Market',
    '8. Partnerships & Impact',
    '9. Risk & Mitigation'
  ]
};

/**
 * Property key mapping for folder IDs.
 */
var FOLDER_KEYS = {
  '_INBOX': 'INBOX_FOLDER_ID',
  '_INDEX': 'INDEX_FOLDER_ID',
  '_CHANGELOG': 'CHANGELOG_FOLDER_ID',
  '1. Company Overview': 'CATEGORY_1_ID',
  '2. Financials': 'CATEGORY_2_ID',
  '3. Legal': 'CATEGORY_3_ID',
  '4. Product': 'CATEGORY_4_ID',
  '5. Market & Competition': 'CATEGORY_5_ID',
  '6. Team': 'CATEGORY_6_ID',
  '7. Go-to-Market': 'CATEGORY_7_ID',
  '8. Partnerships & Impact': 'CATEGORY_8_ID',
  '9. Risk & Mitigation': 'CATEGORY_9_ID'
};

/**
 * Create custom menu when spreadsheet opens.
 */
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('Data Room')
    .addItem('Ask Luna', 'openLunaSidebar')
    .addSeparator()
    .addItem('Setup Folders', 'setupDataRoom')
    .addItem('Sort Inbox', 'sortInboxFiles')
    .addItem('Refresh Index', 'generateIndex')
    .addSeparator()
    .addItem('View Changelog', 'openChangelog')
    .addToUi();
}

/**
 * Bootstrap the entire data room folder structure.
 * Idempotent — safe to run multiple times.
 */
function setupDataRoom() {
  var props = PropertiesService.getScriptProperties();

  // Create or find root folder
  var root = getOrCreateFolder(FOLDER_STRUCTURE.root, DriveApp.getRootFolder());
  props.setProperty('DATA_ROOM_ROOT_ID', root.getId());

  // Create utility folders
  FOLDER_STRUCTURE.utility.forEach(function(name) {
    var folder = getOrCreateFolder(name, root);
    var key = FOLDER_KEYS[name];
    if (key) {
      props.setProperty(key, folder.getId());
    }
  });

  // Create category folders
  FOLDER_STRUCTURE.categories.forEach(function(name) {
    var folder = getOrCreateFolder(name, root);
    var key = FOLDER_KEYS[name];
    if (key) {
      props.setProperty(key, folder.getId());
    }
  });

  // Create Master Index Sheet in _INDEX/
  var indexFolderId = props.getProperty('INDEX_FOLDER_ID');
  createMasterIndexSheet(indexFolderId);

  Logger.log('Data room setup complete. Root folder: ' + root.getUrl());
  try {
    SpreadsheetApp.getUi().alert(
      'Data Room Setup Complete',
      'Created ' + (FOLDER_STRUCTURE.utility.length + FOLDER_STRUCTURE.categories.length) +
      ' folders.\n\nRoot: ' + root.getUrl(),
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  } catch (e) {
    // getUi() not available when run from script editor directly
    Logger.log('Setup complete (run from editor — no UI alert).');
  }
}

/**
 * Get an existing subfolder by name or create it.
 * @param {string} name - Folder name
 * @param {Folder} parent - Parent folder
 * @return {Folder} The found or created folder
 */
function getOrCreateFolder(name, parent) {
  var folders = parent.getFoldersByName(name);
  if (folders.hasNext()) {
    return folders.next();
  }
  return parent.createFolder(name);
}

/**
 * Create the Master Index Sheet if it doesn't exist.
 * @param {string} indexFolderId - ID of the _INDEX/ folder
 */
function createMasterIndexSheet(indexFolderId) {
  var props = PropertiesService.getScriptProperties();
  var existingId = props.getProperty('MASTER_INDEX_SHEET_ID');

  if (existingId) {
    try {
      SpreadsheetApp.openById(existingId);
      return; // Already exists
    } catch (e) {
      // Deleted — recreate
    }
  }

  var ss = SpreadsheetApp.create('Master Index');
  var sheet = ss.getActiveSheet();
  sheet.setName('Master Index');

  // Headers (column A is hidden File ID for deduplication)
  var headers = [
    'File ID', 'File Name', 'Category', 'Subfolder', 'File Type',
    'File Size', 'Created Date', 'Last Modified', 'Direct Link',
    'Tags', 'Status', 'Notes'
  ];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  sheet.setFrozenRows(1);

  // Hide File ID column
  sheet.hideColumns(1);

  // Move to _INDEX/ folder
  var file = DriveApp.getFileById(ss.getId());
  var indexFolder = DriveApp.getFolderById(indexFolderId);
  file.moveTo(indexFolder);

  props.setProperty('MASTER_INDEX_SHEET_ID', ss.getId());
  Logger.log('Created Master Index Sheet: ' + ss.getUrl());
}

/**
 * Open the changelog spreadsheet in a new tab.
 */
function openChangelog() {
  var props = PropertiesService.getScriptProperties();
  var sheetId = props.getProperty('CHANGELOG_SHEET_ID');
  if (sheetId) {
    var url = 'https://docs.google.com/spreadsheets/d/' + sheetId;
    var html = HtmlService.createHtmlOutput(
      '<script>window.open("' + url + '");google.script.host.close();</script>'
    ).setWidth(1).setHeight(1);
    SpreadsheetApp.getUi().showModalDialog(html, 'Opening Changelog...');
  } else {
    SpreadsheetApp.getUi().alert('No changelog found. Run Setup Folders first.');
  }
}




/**
 * changeLogger.gs — Data Room Change Logger
 *
 * Append-only audit trail for all data room operations.
 * Used by inboxSorter.gs and indexGenerator.gs.
 */

var CHANGELOG_SHEET_NAME = 'Changelog';

/**
 * Get or create the changelog spreadsheet in _CHANGELOG/ folder.
 * @return {Spreadsheet} The changelog spreadsheet
 */
function getChangelogSheet() {
  var props = PropertiesService.getScriptProperties();
  var changelogFolderId = props.getProperty('CHANGELOG_FOLDER_ID');

  if (!changelogFolderId) {
    throw new Error('Data room not set up. Run setupDataRoom() first.');
  }

  var sheetId = props.getProperty('CHANGELOG_SHEET_ID');

  if (sheetId) {
    try {
      return SpreadsheetApp.openById(sheetId).getSheetByName(CHANGELOG_SHEET_NAME);
    } catch (e) {
      // Sheet was deleted — recreate below
    }
  }

  // Create new changelog spreadsheet
  var ss = SpreadsheetApp.create('Data Room Changelog');
  var sheet = ss.getActiveSheet();
  sheet.setName(CHANGELOG_SHEET_NAME);

  // Set headers
  sheet.getRange('A1:F1').setValues([[
    'Timestamp', 'Event Type', 'File Name', 'From', 'To', 'User'
  ]]);
  sheet.getRange('A1:F1').setFontWeight('bold');
  sheet.setFrozenRows(1);

  // Column widths
  sheet.setColumnWidth(1, 180); // Timestamp
  sheet.setColumnWidth(2, 120); // Event Type
  sheet.setColumnWidth(3, 300); // File Name
  sheet.setColumnWidth(4, 200); // From
  sheet.setColumnWidth(5, 200); // To
  sheet.setColumnWidth(6, 150); // User

  // Move to _CHANGELOG/ folder
  var file = DriveApp.getFileById(ss.getId());
  var changelogFolder = DriveApp.getFolderById(changelogFolderId);
  file.moveTo(changelogFolder);

  // Store ID for future use
  props.setProperty('CHANGELOG_SHEET_ID', ss.getId());

  return sheet;
}

/**
 * Log a change event to the changelog.
 *
 * @param {string} eventType - SORTED, MODIFIED, ADDED, UNSORTED, ERROR, INDEX_REFRESH
 * @param {string} fileName - Name of the affected file
 * @param {string} fromFolder - Source folder (or '—' if N/A)
 * @param {string} toFolder - Destination folder (or '—' if N/A)
 * @param {string} [user='Script'] - Who triggered the action
 */
function logChange(eventType, fileName, fromFolder, toFolder, user) {
  user = user || 'Script';

  var sheet = getChangelogSheet();
  var timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');

  sheet.appendRow([timestamp, eventType, fileName, fromFolder, toFolder, user]);
}


/**
 * indexGenerator.gs — Master Index Sheet Builder
 *md                 fa                                                     f
 * Crawls the entire data room folder tree (skipping utility folders),
 * builds a searchable Google Sheet with metadata for every file.
 */

/** Folders to skip during crawl. */
var SKIP_FOLDERS = ['_INBOX', '_INDEX', '_CHANGELOG'];

/**
 * Generate or update the Master Index Sheet.
 * Deduplicates by File ID. Updates existing rows, appends new ones.
 */
function generateIndex() {
  var props = PropertiesService.getScriptProperties();
  var rootId = props.getProperty('DATA_ROOM_ROOT_ID');
  var sheetId = props.getProperty('MASTER_INDEX_SHEET_ID');

  if (!rootId || !sheetId) {
    Logger.log('ERROR: Data room not set up. Run setupDataRoom() first.');
    return;
  }

  var ss = SpreadsheetApp.openById(sheetId);
  var sheet = ss.getSheetByName('Master Index');

  // Load existing index keyed by File ID
  var existingIndex = loadExistingIndex(sheet);

  // Crawl data room
  var root = DriveApp.getFolderById(rootId);
  var allFiles = [];
  crawlFolder(root, '', allFiles);

  // Build output rows
  var newRows = [];
  var updatedCount = 0;

  allFiles.forEach(function(fileInfo) {
    if (existingIndex[fileInfo.id]) {
      // Update existing row (keep manual fields: Status, Notes)
      var existing = existingIndex[fileInfo.id];
      existing.row[1] = fileInfo.name;         // File Name
      existing.row[2] = fileInfo.category;      // Category
      existing.row[3] = fileInfo.subfolder;     // Subfolder
      existing.row[4] = fileInfo.mimeType;      // File Type
      existing.row[5] = fileInfo.size;           // File Size
      existing.row[6] = fileInfo.created;        // Created
      existing.row[7] = fileInfo.modified;       // Last Modified
      existing.row[8] = fileInfo.url;            // Direct Link
      existing.row[9] = fileInfo.tags;           // Tags
      // Columns 10 (Status) and 11 (Notes) preserved from existing

      sheet.getRange(existing.rowNum, 1, 1, existing.row.length).setValues([existing.row]);
      updatedCount++;
      delete existingIndex[fileInfo.id]; // Mark as processed
    } else {
      // New file
      newRows.push([
        fileInfo.id,
        fileInfo.name,
        fileInfo.category,
        fileInfo.subfolder,
        fileInfo.mimeType,
        fileInfo.size,
        fileInfo.created,
        fileInfo.modified,
        fileInfo.url,
        fileInfo.tags,
        '',  // Status (manual)
        ''   // Notes (manual)
      ]);
    }
  });

  // Append new rows
  if (newRows.length > 0) {
    var startRow = sheet.getLastRow() + 1;
    sheet.getRange(startRow, 1, newRows.length, 12).setValues(newRows);
  }

  // Apply formatting
  applyConditionalFormatting(sheet);
  updateCoverageSummary(sheet, allFiles);

  // Log (non-fatal — index is already saved above)
  try {
    logChange('INDEX_REFRESH', 'Master Index', '—',
      allFiles.length + ' files indexed (' + newRows.length + ' new, ' + updatedCount + ' updated)',
      'Script');
  } catch (e) {
    Logger.log('Warning: changelog logging failed: ' + e.message);
  }

  Logger.log('Index generated: ' + allFiles.length + ' files. New: ' + newRows.length + ', Updated: ' + updatedCount);
}

/**
 * Load existing index data from the sheet, keyed by File ID.
 * @param {Sheet} sheet - The Master Index sheet
 * @return {Object} Map of fileId → {row: array, rowNum: number}
 */
function loadExistingIndex(sheet) {
  var index = {};
  var lastRow = sheet.getLastRow();

  if (lastRow <= 1) return index; // Only headers

  var data = sheet.getRange(2, 1, lastRow - 1, 12).getValues();

  data.forEach(function(row, i) {
    var fileId = row[0];
    if (fileId) {
      index[fileId] = {
        row: row,
        rowNum: i + 2 // 1-indexed, skip header
      };
    }
  });

  return index;
}

/**
 * Recursively crawl a folder and collect file metadata.
 * @param {Folder} folder - Current folder
 * @param {string} parentCategory - Parent category name (empty for root)
 * @param {Array} results - Accumulator for file info objects
 */
function crawlFolder(folder, parentCategory, results) {
  var folderName = folder.getName();

  // Skip utility folders
  if (SKIP_FOLDERS.indexOf(folderName) >= 0) return;

  // Determine category and subfolder
  var category = parentCategory || folderName;
  var subfolder = parentCategory ? folderName : '';

  // Don't index files in the root data room folder itself
  if (parentCategory || folderName !== '[Project Tapestry] Data Room') {
    // Process files in this folder
    var files = folder.getFiles();
    while (files.hasNext()) {
      var file = files.next();
      results.push({
        id: file.getId(),
        name: file.getName(),
        category: category,
        subfolder: subfolder,
        mimeType: friendlyMimeType(file.getMimeType()),
        size: formatFileSize(file.getSize()),
        created: formatDate(file.getDateCreated()),
        modified: formatDate(file.getLastUpdated()),
        url: file.getUrl(),
        tags: generateTags(category, subfolder, file.getName())
      });
    }
  }

  // Recurse into subfolders
  var subfolders = folder.getFolders();
  while (subfolders.hasNext()) {
    var sub = subfolders.next();
    // For top-level category folders, pass their name as the category
    var nextCategory = parentCategory ? category : sub.getName();
    crawlFolder(sub, nextCategory, results);
  }
}

/**
 * Convert MIME type to human-readable format.
 */
function friendlyMimeType(mime) {
  var map = {
    'application/vnd.google-apps.document': 'Google Doc',
    'application/vnd.google-apps.spreadsheet': 'Google Sheet',
    'application/vnd.google-apps.presentation': 'Google Slides',
    'application/vnd.google-apps.form': 'Google Form',
    'application/pdf': 'PDF',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint',
    'image/png': 'PNG',
    'image/jpeg': 'JPEG',
    'text/plain': 'Text',
    'text/csv': 'CSV'
  };
  return map[mime] || mime;
}

/**
 * Format file size in human-readable units.
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '—'; // Google-native files report 0 bytes
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Format date for display.
 */
function formatDate(date) {
  return Utilities.formatDate(date, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');
}

/**
 * Auto-generate tags from folder path and filename.
 */
function generateTags(category, subfolder, fileName) {
  var tags = [];

  // Category-based tags
  var categoryTag = category.replace(/^\d+\.\s*/, '').toLowerCase().replace(/\s+&\s+/g, ', ');
  tags.push(categoryTag);

  if (subfolder) {
    tags.push(subfolder.toLowerCase());
  }

  return tags.join(', ');
}

/**
 * Apply conditional formatting based on Status column (K).
 */
function applyConditionalFormatting(sheet) {
  // Clear existing conditional format rules
  sheet.clearConditionalFormatRules();

  var lastRow = Math.max(sheet.getLastRow(), 2);
  var statusRange = sheet.getRange('K2:K' + lastRow);

  var rules = [];

  // Draft = yellow
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Draft')
    .setBackground('#FFF9C4')
    .setRanges([statusRange])
    .build());

  // Needs Review = orange
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Needs Review')
    .setBackground('#FFE0B2')
    .setRanges([statusRange])
    .build());

  // Final = green
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Final')
    .setBackground('#C8E6C9')
    .setRanges([statusRange])
    .build());

  sheet.setConditionalFormatRules(rules);
}

/**
 * Add a coverage summary showing which categories have files.
 * Uses a named range or cell note on A1 to avoid interfering with data.
 */
function updateCoverageSummary(sheet, allFiles) {
  var categories = {};
  allFiles.forEach(function(f) {
    categories[f.category] = (categories[f.category] || 0) + 1;
  });

  var total = 9; // 9 data room categories
  var populated = Object.keys(categories).length;

  var summary = populated + ' of ' + total + ' categories have files | ' +
    allFiles.length + ' total documents | Last refreshed: ' +
    Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');

  // Store as note on B1 (File Name header) so it's visible but doesn't break data
  sheet.getRange('B1').setNote(summary);
  Logger.log('Coverage: ' + summary);
}








/**
 * inboxSorter.gs — Prefix-Based File Routing
 *
 * Watches _INBOX/ and routes files to the correct category folder
 * based on filename prefix conventions.
 *
 * Trigger: time-based (every 15 minutes) or manual via Data Room menu.
 */

/**
 * Prefix → PropertiesService key mapping.
 * Files named "FINANCE_cap_table.xlsx" route to the folder stored under CATEGORY_2_ID.
 */
var PREFIX_ROUTES = {
  'OVERVIEW_':  'CATEGORY_1_ID',   // 1. Company Overview
  'FINANCE_':   'CATEGORY_2_ID',   // 2. Financials
  'LEGAL_':     'CATEGORY_3_ID',   // 3. Legal
  'PRODUCT_':   'CATEGORY_4_ID',   // 4. Product
  'MARKET_':    'CATEGORY_5_ID',   // 5. Market & Competition
  'TEAM_':      'CATEGORY_6_ID',   // 6. Team
  'GTM_':       'CATEGORY_7_ID',   // 7. Go-to-Market
  'PARTNER_':   'CATEGORY_8_ID',   // 8. Partnerships & Impact
  'RISK_':      'CATEGORY_9_ID'    // 9. Risk & Mitigation
};

/**
 * Scan _INBOX/ and route files based on filename prefix.
 * Safe to call repeatedly — only processes files currently in _INBOX.
 */
function sortInboxFiles() {
  var props = PropertiesService.getScriptProperties();
  var inboxId = props.getProperty('INBOX_FOLDER_ID');

  if (!inboxId) {
    Logger.log('ERROR: Data room not set up. Run setupDataRoom() first.');
    return;
  }

  var inbox = DriveApp.getFolderById(inboxId);
  var files = inbox.getFiles();
  var sorted = 0;
  var unsorted = 0;

  while (files.hasNext()) {
    var file = files.next();
    var fileName = file.getName();

    try {
      var route = matchPrefix(fileName);

      if (route) {
        var targetFolderId = props.getProperty(route.propertyKey);
        if (!targetFolderId) {
          logChange('ERROR', fileName, '_INBOX', '—', 'Script');
          Logger.log('ERROR: Missing folder ID for ' + route.propertyKey);
          continue;
        }

        var targetFolder = DriveApp.getFolderById(targetFolderId);

        // Move file to target folder
        file.moveTo(targetFolder);

        // Strip prefix from filename
        var cleanName = fileName.substring(route.prefix.length);
        if (cleanName) {
          file.setName(cleanName);
        }

        logChange('SORTED', fileName, '_INBOX', targetFolder.getName(), 'Script');
        Logger.log('SORTED: ' + fileName + ' → ' + targetFolder.getName());
        sorted++;

      } else {
        logChange('UNSORTED', fileName, '_INBOX', '_INBOX', 'Script');
        Logger.log('UNSORTED: ' + fileName + ' (no matching prefix)');
        unsorted++;
      }

    } catch (e) {
      logChange('ERROR', fileName, '_INBOX', 'ERROR: ' + e.message, 'Script');
      Logger.log('ERROR processing ' + fileName + ': ' + e.message);
    }
  }

  Logger.log('Inbox sort complete. Sorted: ' + sorted + ', Unsorted: ' + unsorted);
}

/**
 * Match a filename against known prefixes.
 * Case-insensitive matching.
 *
 * @param {string} fileName - The file name to check
 * @return {Object|null} {prefix, propertyKey} or null if no match
 */
function matchPrefix(fileName) {
  var upper = fileName.toUpperCase();

  var prefixes = Object.keys(PREFIX_ROUTES);
  for (var i = 0; i < prefixes.length; i++) {
    if (upper.indexOf(prefixes[i]) === 0) {
      return {
        prefix: prefixes[i],
        propertyKey: PREFIX_ROUTES[prefixes[i]]
      };
    }
  }

  return null;
}

/**
 * Set up time-based trigger for inbox sorting (every 15 minutes).
 * Run once manually to install the trigger.
 */
function installInboxTrigger() {
  // Remove existing triggers for this function
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'sortInboxFiles') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  // Create new trigger
  ScriptApp.newTrigger('sortInboxFiles')
    .timeBased()
    .everyMinutes(15)
    .create();

  Logger.log('Installed inbox sort trigger: every 15 minutes');
}
