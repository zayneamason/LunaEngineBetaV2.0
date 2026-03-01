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
  root: '[Project Eclipse] Data Room',
  utility: ['_INBOX', '_INDEX', '_CHANGELOG'],
  categories: [
    '0 — Demo',
    '1 — What Is Luna',
    '2 — Proof',
    '3 — Team',
    '4 — How It Works',
    '5 — The Money',
    '6 — What We Need',
    'Deep Cuts'
  ]
};

/**
 * Property key mapping for folder IDs.
 */
var FOLDER_KEYS = {
  '_INBOX': 'INBOX_FOLDER_ID',
  '_INDEX': 'INDEX_FOLDER_ID',
  '_CHANGELOG': 'CHANGELOG_FOLDER_ID',
  '0 — Demo': 'CATEGORY_0_ID',
  '1 — What Is Luna': 'CATEGORY_1_ID',
  '2 — Proof': 'CATEGORY_2_ID',
  '3 — Team': 'CATEGORY_3_ID',
  '4 — How It Works': 'CATEGORY_4_ID',
  '5 — The Money': 'CATEGORY_5_ID',
  '6 — What We Need': 'CATEGORY_6_ID',
  'Deep Cuts': 'CATEGORY_DEEP_ID'
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
    .addSeparator()
    .addItem('Archive & Reset', 'archiveDataRoom')
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


// ═══════════════════════════════════════════════════════════════
//  changeLogger.gs — Data Room Change Logger
// ═══════════════════════════════════════════════════════════════

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

  var ss = SpreadsheetApp.create('Data Room Changelog');
  var sheet = ss.getActiveSheet();
  sheet.setName(CHANGELOG_SHEET_NAME);

  sheet.getRange('A1:F1').setValues([[
    'Timestamp', 'Event Type', 'File Name', 'From', 'To', 'User'
  ]]);
  sheet.getRange('A1:F1').setFontWeight('bold');
  sheet.setFrozenRows(1);

  sheet.setColumnWidth(1, 180);
  sheet.setColumnWidth(2, 120);
  sheet.setColumnWidth(3, 300);
  sheet.setColumnWidth(4, 200);
  sheet.setColumnWidth(5, 200);
  sheet.setColumnWidth(6, 150);

  var file = DriveApp.getFileById(ss.getId());
  var changelogFolder = DriveApp.getFolderById(changelogFolderId);
  file.moveTo(changelogFolder);

  props.setProperty('CHANGELOG_SHEET_ID', ss.getId());

  return sheet;
}

/**
 * Log a change event to the changelog.
 */
function logChange(eventType, fileName, fromFolder, toFolder, user) {
  user = user || 'Script';
  var sheet = getChangelogSheet();
  var timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
  sheet.appendRow([timestamp, eventType, fileName, fromFolder, toFolder, user]);
}


// ═══════════════════════════════════════════════════════════════
//  indexGenerator.gs — Master Index Sheet Builder
// ═══════════════════════════════════════════════════════════════

/** Folders to skip during crawl. */
var SKIP_FOLDERS = ['_INBOX', '_INDEX', '_CHANGELOG'];

/**
 * Generate or update the Master Index Sheet.
 * Deduplicates by File ID. Updates existing rows, appends new ones.
 * Removes stale rows for files no longer in the data room.
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

  var existingIndex = loadExistingIndex(sheet);

  var root = DriveApp.getFolderById(rootId);
  var allFiles = [];
  crawlFolder(root, '', allFiles);

  var newRows = [];
  var updatedCount = 0;

  allFiles.forEach(function(fileInfo) {
    if (existingIndex[fileInfo.id]) {
      var existing = existingIndex[fileInfo.id];
      existing.row[1] = fileInfo.name;
      existing.row[2] = fileInfo.category;
      existing.row[3] = fileInfo.subfolder;
      existing.row[4] = fileInfo.mimeType;
      existing.row[5] = fileInfo.size;
      existing.row[6] = fileInfo.created;
      existing.row[7] = fileInfo.modified;
      existing.row[8] = fileInfo.url;
      existing.row[9] = fileInfo.tags;

      sheet.getRange(existing.rowNum, 1, 1, existing.row.length).setValues([existing.row]);
      updatedCount++;
      delete existingIndex[fileInfo.id];
    } else {
      newRows.push([
        fileInfo.id, fileInfo.name, fileInfo.category, fileInfo.subfolder,
        fileInfo.mimeType, fileInfo.size, fileInfo.created, fileInfo.modified,
        fileInfo.url, fileInfo.tags, '', ''
      ]);
    }
  });

  // Remove stale rows (bottom-up so row numbers stay valid)
  var staleIds = Object.keys(existingIndex);
  var removedCount = 0;
  if (staleIds.length > 0) {
    var staleRows = staleIds.map(function(id) { return existingIndex[id].rowNum; });
    staleRows.sort(function(a, b) { return b - a; });
    for (var r = 0; r < staleRows.length; r++) {
      sheet.deleteRow(staleRows[r]);
      removedCount++;
    }
  }

  if (newRows.length > 0) {
    var startRow = sheet.getLastRow() + 1;
    sheet.getRange(startRow, 1, newRows.length, 12).setValues(newRows);
  }

  applyConditionalFormatting(sheet);
  updateCoverageSummary(sheet, allFiles);

  try {
    logChange('INDEX_REFRESH', 'Master Index', '—',
      allFiles.length + ' files (' + newRows.length + ' new, ' + updatedCount + ' updated, ' + removedCount + ' removed)',
      'Script');
  } catch (e) {
    Logger.log('Warning: changelog logging failed: ' + e.message);
  }

  Logger.log('Index: ' + allFiles.length + ' files. New: ' + newRows.length + ', Updated: ' + updatedCount + ', Removed: ' + removedCount);
}

function loadExistingIndex(sheet) {
  var index = {};
  var lastRow = sheet.getLastRow();
  if (lastRow <= 1) return index;

  var data = sheet.getRange(2, 1, lastRow - 1, 12).getValues();
  data.forEach(function(row, i) {
    var fileId = row[0];
    if (fileId) {
      index[fileId] = { row: row, rowNum: i + 2 };
    }
  });
  return index;
}

function crawlFolder(folder, parentCategory, results) {
  var folderName = folder.getName();
  if (SKIP_FOLDERS.indexOf(folderName) >= 0) return;

  var category = parentCategory || folderName;
  var subfolder = parentCategory ? folderName : '';

  if (parentCategory || folderName !== '[Project Eclipse] Data Room') {
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

  var subfolders = folder.getFolders();
  while (subfolders.hasNext()) {
    var sub = subfolders.next();
    var nextCategory = parentCategory ? category : sub.getName();
    crawlFolder(sub, nextCategory, results);
  }
}

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

function formatFileSize(bytes) {
  if (bytes === 0) return '—';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(date) {
  return Utilities.formatDate(date, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');
}

function generateTags(category, subfolder, fileName) {
  var tags = [];
  var categoryTag = category.replace(/^\d+\s*[—–\-\.]\s*/, '').toLowerCase().replace(/\s+&\s+/g, ', ');
  tags.push(categoryTag);
  if (subfolder) {
    tags.push(subfolder.toLowerCase());
  }
  return tags.join(', ');
}

function applyConditionalFormatting(sheet) {
  sheet.clearConditionalFormatRules();
  var lastRow = Math.max(sheet.getLastRow(), 2);
  var statusRange = sheet.getRange('K2:K' + lastRow);

  var rules = [];
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Draft').setBackground('#FFF9C4').setRanges([statusRange]).build());
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Needs Review').setBackground('#FFE0B2').setRanges([statusRange]).build());
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Final').setBackground('#C8E6C9').setRanges([statusRange]).build());

  sheet.setConditionalFormatRules(rules);
}

function updateCoverageSummary(sheet, allFiles) {
  var categories = {};
  allFiles.forEach(function(f) {
    categories[f.category] = (categories[f.category] || 0) + 1;
  });

  var total = 8; // 8 rooms (0-6 + Deep Cuts)
  var populated = Object.keys(categories).length;

  var summary = populated + ' of ' + total + ' rooms have files | ' +
    allFiles.length + ' total documents | Last refreshed: ' +
    Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');

  sheet.getRange('B1').setNote(summary);
  Logger.log('Coverage: ' + summary);
}


// ═══════════════════════════════════════════════════════════════
//  inboxSorter.gs — Prefix-Based File Routing
// ═══════════════════════════════════════════════════════════════

var PREFIX_ROUTES = {
  'DEMO_':    'CATEGORY_0_ID',   // 0 — Demo
  'LUNA_':    'CATEGORY_1_ID',   // 1 — What Is Luna
  'PROOF_':   'CATEGORY_2_ID',   // 2 — Proof
  'TEAM_':    'CATEGORY_3_ID',   // 3 — Team
  'TECH_':    'CATEGORY_4_ID',   // 4 — How It Works
  'MONEY_':   'CATEGORY_5_ID',   // 5 — The Money
  'ASK_':     'CATEGORY_6_ID',   // 6 — What We Need
  'DEEP_':    'CATEGORY_DEEP_ID' // Deep Cuts
};

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
          continue;
        }

        var targetFolder = DriveApp.getFolderById(targetFolderId);
        file.moveTo(targetFolder);

        var cleanName = fileName.substring(route.prefix.length);
        if (cleanName) {
          file.setName(cleanName);
        }

        logChange('SORTED', fileName, '_INBOX', targetFolder.getName(), 'Script');
        sorted++;
      } else {
        logChange('UNSORTED', fileName, '_INBOX', '_INBOX', 'Script');
        unsorted++;
      }
    } catch (e) {
      logChange('ERROR', fileName, '_INBOX', 'ERROR: ' + e.message, 'Script');
    }
  }

  Logger.log('Inbox sort complete. Sorted: ' + sorted + ', Unsorted: ' + unsorted);
}

function matchPrefix(fileName) {
  var upper = fileName.toUpperCase();
  var prefixes = Object.keys(PREFIX_ROUTES);
  for (var i = 0; i < prefixes.length; i++) {
    if (upper.indexOf(prefixes[i]) === 0) {
      return { prefix: prefixes[i], propertyKey: PREFIX_ROUTES[prefixes[i]] };
    }
  }
  return null;
}

function installInboxTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'sortInboxFiles') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger('sortInboxFiles')
    .timeBased()
    .everyMinutes(15)
    .create();

  Logger.log('Installed inbox sort trigger: every 15 minutes');
}


// ═══════════════════════════════════════════════════════════════
//  Archive & Reset — Move everything to archive, start clean
// ═══════════════════════════════════════════════════════════════

/**
 * Archive destination folder.
 * Will be renamed to "_ARCHIVE — Pre-Reset (Feb 2026)" before use.
 */
var ARCHIVE_FOLDER_ID = '1Y9TY7m5tR_iLQYKd0Q9X6zxRKX2RF8rN';

/**
 * Folders to archive (move into archive folder with all contents).
 * Includes both Eclipse category folders and any surviving Tapestry folders.
 */
var ARCHIVE_FOLDERS = [
  '0 — Demo',
  '1 — What Is Luna',
  '2 — Traction & Partnerships',
  '3 — Team',
  '4 — Technology',
  '5 — Financials',
  '6 — What We Need',
  'Reference Library',
  // Surviving Tapestry folders
  '4. Product'
];

/**
 * Archive the entire data room and reset to empty.
 *
 * 1. Renames archive folder to "_ARCHIVE — Pre-Reset (Feb 2026)"
 * 2. Moves all category folders (with contents) into the archive
 * 3. Moves any loose files in the data room root into the archive
 * 4. Creates an ARCHIVE INDEX doc listing everything moved
 * 5. Leaves _INBOX, _INDEX, _CHANGELOG in place
 *
 * After running: run setupDataRoom() to create the new empty room folders.
 * Then run generateIndex() to clear the Master Index.
 */
function archiveDataRoom() {
  var props = PropertiesService.getScriptProperties();
  var rootId = props.getProperty('DATA_ROOM_ROOT_ID');

  if (!rootId) {
    Logger.log('ERROR: Data room not set up.');
    return;
  }

  var root = DriveApp.getFolderById(rootId);
  var archiveFolder = DriveApp.getFolderById(ARCHIVE_FOLDER_ID);

  // Step 1: Rename archive folder
  archiveFolder.setName('_ARCHIVE — Pre-Reset (Feb 2026)');
  Logger.log('Renamed archive folder');

  var movedFolders = [];
  var movedFiles = [];

  // Step 2: Move category folders
  ARCHIVE_FOLDERS.forEach(function(name) {
    var folders = root.getFoldersByName(name);
    while (folders.hasNext()) {
      var folder = folders.next();

      // Build contents manifest
      var contents = [];
      var files = folder.getFiles();
      while (files.hasNext()) {
        var f = files.next();
        contents.push(f.getName() + ' (' + friendlyMimeType(f.getMimeType()) + ')');
      }
      var subs = folder.getFolders();
      while (subs.hasNext()) {
        var sub = subs.next();
        var subContents = [];
        var subFiles = sub.getFiles();
        while (subFiles.hasNext()) {
          subContents.push(subFiles.next().getName());
        }
        contents.push(sub.getName() + '/ (' + subContents.length + ' files: ' + subContents.join(', ') + ')');
      }

      folder.moveTo(archiveFolder);
      movedFolders.push({ name: name, contents: contents });
      Logger.log('ARCHIVED: ' + name + '/ (' + contents.length + ' items)');
    }
  });

  // Step 3: Move loose files in root
  var rootFiles = root.getFiles();
  while (rootFiles.hasNext()) {
    var file = rootFiles.next();
    var fileName = file.getName();
    file.moveTo(archiveFolder);
    movedFiles.push(fileName);
    Logger.log('ARCHIVED loose file: ' + fileName);
  }

  // Step 4: Create ARCHIVE INDEX doc
  var indexBody = 'ARCHIVE INDEX — Project Eclipse Data Room\n' +
    'Archived: February 27, 2026\n' +
    'Reason: Vision inconsistency across documents. Starting fresh from Calvin\'s Playbook as single source of truth.\n\n' +
    'CONTENTS:\n\n';

  movedFolders.forEach(function(f) {
    indexBody += f.name + '/\n';
    f.contents.forEach(function(item) {
      indexBody += '  - ' + item + '\n';
    });
    indexBody += '\n';
  });

  if (movedFiles.length > 0) {
    indexBody += 'Loose files (from data room root):\n';
    movedFiles.forEach(function(name) {
      indexBody += '  - ' + name + '\n';
    });
    indexBody += '\n';
  }

  indexBody += 'NOTE: Nothing here is deleted. It\'s archived for reference.\n' +
    'The 7 draft docs are superseded — do not use them as source material for new documents.\n' +
    'Calvin\'s Playbook is the single source of truth for all new content.';

  var indexDoc = DocumentApp.create('ARCHIVE INDEX');
  var body = indexDoc.getBody();
  var paragraphs = indexBody.split('\n');
  for (var p = 0; p < paragraphs.length; p++) {
    if (p > 0) {
      body.appendParagraph(paragraphs[p]);
    } else {
      body.getChild(0).asParagraph().setText(paragraphs[p]);
    }
  }
  indexDoc.saveAndClose();

  var indexFile = DriveApp.getFileById(indexDoc.getId());
  archiveFolder.addFile(indexFile);
  DriveApp.getRootFolder().removeFile(indexFile);

  // Log
  var summary = 'Archived ' + movedFolders.length + ' folders and ' + movedFiles.length + ' loose files.\n' +
    'Archive folder: _ARCHIVE — Pre-Reset (Feb 2026)\n\n' +
    'Next steps:\n1. Run "Setup Folders" to create new empty rooms\n2. Run "Refresh Index" to clear the Master Index';

  Logger.log(summary);

  try {
    logChange('ARCHIVE', 'Full data room archive', '—', summary, 'Script');
  } catch (e) {
    Logger.log('Warning: changelog logging failed: ' + e.message);
  }

  try {
    SpreadsheetApp.getUi().alert('Archive Complete', summary, SpreadsheetApp.getUi().ButtonSet.OK);
  } catch (e) {}
}
