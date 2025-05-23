// netlify/functions/chat.js
// This serverless function handles OpenAI API calls securely

exports.handler = async (event, context) => {
  // Only allow POST requests
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: 'Method not allowed' })
    };
  }

  // Parse request body
  const { action, data } = JSON.parse(event.body);

  // Get API key from environment variable
  const API_KEY = process.env.OPENAI_API_KEY;
  const ASSISTANT_ID = process.env.ASSISTANT_ID || 'asst_2DJx5MSWeR7MxT5Oe7941E0j';
  const VECTOR_STORE_ID = process.env.VECTOR_STORE_ID || 'vs_6830e783e0bc8191809badf4bc5655ae';

  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };

  try {
    let response;

    switch (action) {
      case 'createThread':
        response = await fetch('https://api.openai.com/v1/threads', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${API_KEY}`,
            'Content-Type': 'application/json',
            'OpenAI-Beta': 'assistants=v2'
          }
        });
        break;

      case 'sendMessage':
        const { threadId, message } = data;
        
        // Add message to thread
        await fetch(`https://api.openai.com/v1/threads/${threadId}/messages`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${API_KEY}`,
            'Content-Type': 'application/json',
            'OpenAI-Beta': 'assistants=v2'
          },
          body: JSON.stringify({
            role: 'user',
            content: message
          })
        });

        // Run assistant
        response = await fetch(`https://api.openai.com/v1/threads/${threadId}/runs`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${API_KEY}`,
            'Content-Type': 'application/json',
            'OpenAI-Beta': 'assistants=v2'
          },
          body: JSON.stringify({
            assistant_id: ASSISTANT_ID
          })
        });
        break;

      case 'checkRunStatus':
        const { threadId: tid, runId } = data;
        response = await fetch(
          `https://api.openai.com/v1/threads/${tid}/runs/${runId}`,
          {
            headers: {
              'Authorization': `Bearer ${API_KEY}`,
              'OpenAI-Beta': 'assistants=v2'
            }
          }
        );
        break;

      case 'getMessages':
        const { threadId: thread } = data;
        response = await fetch(
          `https://api.openai.com/v1/threads/${thread}/messages`,
          {
            headers: {
              'Authorization': `Bearer ${API_KEY}`,
              'OpenAI-Beta': 'assistants=v2'
            }
          }
        );
        break;

      default:
        return {
          statusCode: 400,
          headers,
          body: JSON.stringify({ error: 'Invalid action' })
        };
    }

    const result = await response.json();

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify(result)
    };

  } catch (error) {
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: error.message })
    };
  }
};

// Package.json for Netlify Functions
// Save as: package.json in your repository root
const packageJson = {
  "name": "msps-chatbot",
  "version": "1.0.0",
  "description": "MSPS Gluten Free Chatbot",
  "scripts": {
    "build": "echo 'No build required'"
  },
  "dependencies": {
    "node-fetch": "^2.6.7"
  }
};

// netlify.toml - Netlify configuration
// Save as: netlify.toml in your repository root
const netlifyConfig = `
[build]
  functions = "netlify/functions"

[build.environment]
  NODE_VERSION = "18"

[[headers]]
  for = "/*"
  [headers.values]
    Access-Control-Allow-Origin = "*"
`;

// Updated frontend code to use Netlify Functions
// This replaces the API calls in the HTML file
const secureApiCalls = `
// Replace the direct OpenAI API calls with these secure function calls

async function createThread() {
    const response = await fetch('/.netlify/functions/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'createThread' })
    });
    const data = await response.json();
    return data.id;
}

async function sendMessageSecure(threadId, message) {
    // Send message
    const runResponse = await fetch('/.netlify/functions/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'sendMessage',
            data: { threadId, message }
        })
    });
    const run = await runResponse.json();
    
    // Poll for completion
    let runStatus = run;
    while (runStatus.status !== 'completed') {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const statusResponse = await fetch('/.netlify/functions/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'checkRunStatus',
                data: { threadId, runId: run.id }
            })
        });
        
        runStatus = await statusResponse.json();
        
        if (runStatus.status === 'failed') {
            throw new Error('Assistant run failed');
        }
    }
    
    // Get messages
    const messagesResponse = await fetch('/.netlify/functions/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'getMessages',
            data: { threadId }
        })
    });
    
    return await messagesResponse.json();
}
`;
