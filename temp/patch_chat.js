const fs = require('fs');
const file = 'agents/social_agent/static/social_agent/js/chat.js';
let content = fs.readFileSync(file, 'utf8');

// Add minimum length validation check
content = content.replace(
    'if (!prompt) return;',
    'if (!prompt) return;\n        if (prompt.length < 5) {\n            appendMessage(\'AG\', \'Please provide a more detailed campaign objective (at least 5 characters).\', \'agent-msg\');\n            return;\n        }'
);

// Improve error message display instead of raw JSON
content = content.replace(
    'appendMessage(\'AG\', `Error initializing workflow: ${JSON.stringify(err)}`, \'agent-msg\');',
    `let errorMsg = 'Failed to initialize workflow.';
                if (err.prompt) {
                    errorMsg = \`Hold on, I need more information: \${err.prompt[0]}\`;
                } else {
                    errorMsg = \`Error: \${JSON.stringify(err)}\`;
                }
                appendMessage('AG', errorMsg, 'agent-msg');`
);

fs.writeFileSync(file, content);
