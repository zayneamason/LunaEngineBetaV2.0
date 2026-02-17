/**
 * Claude.ai COMPLETE Conversation Exporter
 *
 * Fetches ALL conversations from your Claude.ai account (not just cached ones).
 * This script will paginate through your entire conversation history.
 *
 * Usage:
 * 1. Open https://claude.ai in your browser
 * 2. Open Developer Console (F12 or Cmd+Option+J)
 * 3. Paste this entire script and press Enter
 * 4. Wait for export to complete (may take several minutes for large histories)
 */

(async function() {
    console.log('Claude.ai COMPLETE Conversation Exporter');
    console.log('==========================================\n');
    console.log('This will fetch EVERY conversation from your account.\n');

    // Get organization ID from current page
    const getOrgId = () => {
        // Try to extract from URL or page data
        const match = window.location.pathname.match(/\/org\/([^\/]+)/);
        if (match) return match[1];

        // Try to get from localStorage
        const keys = Object.keys(localStorage);
        for (const key of keys) {
            if (key.includes('organization')) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    if (data.uuid) return data.uuid;
                } catch (e) {}
            }
        }
        return null;
    };

    const orgId = getOrgId();
    console.log(`Organization ID: ${orgId || 'Not found'}\n`);

    // Function to fetch ALL conversation UUIDs from API (with pagination)
    async function fetchAllConversationList() {
        const allConversations = [];
        let hasMore = true;
        let offset = 0;
        const limit = 50; // Fetch 50 at a time

        console.log('Step 1: Fetching complete conversation list...\n');

        while (hasMore) {
            const url = orgId
                ? `https://api.claude.ai/api/organizations/${orgId}/chat_conversations?limit=${limit}&offset=${offset}`
                : `https://api.claude.ai/api/chat_conversations?limit=${limit}&offset=${offset}`;

            try {
                console.log(`  Fetching conversations ${offset + 1} to ${offset + limit}...`);
                const response = await fetch(url, {
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                const conversations = data.conversations || data;

                if (Array.isArray(conversations) && conversations.length > 0) {
                    allConversations.push(...conversations);
                    console.log(`  ✓ Found ${conversations.length} conversations (total so far: ${allConversations.length})`);

                    // Check if there are more
                    hasMore = conversations.length === limit;
                    offset += limit;

                    // Rate limiting
                    if (hasMore) {
                        await new Promise(resolve => setTimeout(resolve, 500));
                    }
                } else {
                    hasMore = false;
                }
            } catch (error) {
                console.error(`  ✗ Failed to fetch conversation list:`, error.message);
                hasMore = false;
            }
        }

        return allConversations;
    }

    // Fetch complete list
    const conversations = await fetchAllConversationList();
    const conversationUUIDs = conversations.map(conv => conv.uuid);

    console.log(`\n✓ Found ${conversationUUIDs.length} TOTAL conversations in your account!\n`);
    console.log('=' .repeat(80));

    if (conversationUUIDs.length === 0) {
        console.error('ERROR: No conversations found. Make sure you are logged into Claude.ai');
        return;
    }

    // Show some stats
    const withNames = conversations.filter(c => c.name && c.name.trim() !== '').length;
    const starred = conversations.filter(c => c.is_starred).length;
    console.log(`\nConversation Stats:`);
    console.log(`  Total: ${conversationUUIDs.length}`);
    console.log(`  Named: ${withNames}`);
    console.log(`  Starred: ${starred}`);
    console.log('');

    // Function to fetch a conversation's full content
    async function fetchConversation(uuid) {
        const url = orgId
            ? `https://api.claude.ai/api/organizations/${orgId}/chat_conversations/${uuid}`
            : `https://api.claude.ai/api/chat_conversations/${uuid}`;

        try {
            const response = await fetch(url, {
                credentials: 'include',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`Failed to fetch ${uuid}:`, error.message);
            return null;
        }
    }

    // Function to format conversation as text
    function formatConversation(data) {
        if (!data) return '';

        const lines = [];
        lines.push(`Conversation: ${data.name || 'Untitled'}`);
        lines.push(`UUID: ${data.uuid}`);
        lines.push(`Created: ${data.created_at}`);
        lines.push(`Updated: ${data.updated_at}`);
        if (data.is_starred) lines.push(`Starred: Yes`);
        lines.push('='.repeat(80));
        lines.push('');

        for (const msg of data.chat_messages || []) {
            const sender = (msg.sender || 'unknown').toUpperCase();
            const timestamp = msg.created_at || '';
            const text = msg.text || '';

            lines.push(`[${sender}] ${timestamp}`);
            lines.push(text);
            lines.push('');
            lines.push('-'.repeat(80));
            lines.push('');
        }

        return lines.join('\n');
    }

    // Export all conversations
    console.log('=' .repeat(80));
    console.log('\nStep 2: Fetching full content for each conversation...\n');
    const allTranscripts = {};
    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < conversationUUIDs.length; i++) {
        const uuid = conversationUUIDs[i];
        const convInfo = conversations[i];
        const displayName = (convInfo.name || 'Untitled').substring(0, 50);

        console.log(`[${i + 1}/${conversationUUIDs.length}] ${displayName}...`);

        const data = await fetchConversation(uuid);
        if (data) {
            allTranscripts[uuid] = {
                raw: data,
                text: formatConversation(data),
                metadata: {
                    name: data.name,
                    created_at: data.created_at,
                    updated_at: data.updated_at,
                    message_count: (data.chat_messages || []).length,
                    is_starred: data.is_starred || false
                }
            };
            successCount++;
            console.log(`  ✓ ${(data.chat_messages || []).length} messages`);
        } else {
            failCount++;
            console.log(`  ✗ Failed`);
        }

        // Rate limiting - be respectful to the API
        if (i < conversationUUIDs.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 500));
        }

        // Progress update every 10 conversations
        if ((i + 1) % 10 === 0) {
            console.log(`\n--- Progress: ${i + 1}/${conversationUUIDs.length} (${Math.round((i + 1) / conversationUUIDs.length * 100)}%) ---\n`);
        }
    }

    console.log('\n' + '='.repeat(80));
    console.log(`Export complete!`);
    console.log(`  Success: ${successCount}`);
    console.log(`  Failed: ${failCount}`);
    console.log(`  Total: ${conversationUUIDs.length}`);
    console.log('='.repeat(80) + '\n');

    // Prepare download
    const exportData = {
        timestamp: new Date().toISOString(),
        total_conversations: conversationUUIDs.length,
        successful: successCount,
        failed: failCount,
        conversations: allTranscripts
    };

    // Create downloadable file
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `claude_transcripts_COMPLETE_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log('✓ Downloaded: ' + a.download);
    console.log(`\nFile size: ~${(blob.size / 1024 / 1024).toFixed(2)} MB`);
    console.log('\nNext steps:');
    console.log('1. Move the JSON file to: Tools/MemoryMatrix_SandBox/_CLAUDE_TRANSCRIPTS/');
    console.log('2. Run: python3 scripts/organize_transcripts.py');
    console.log('3. Your transcripts will be organized by date!\n');

    return exportData;
})();
