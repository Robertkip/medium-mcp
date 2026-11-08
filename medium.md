
Step 1: Understand Medium API Requirements

Medium provides an official REST API to manage posts. Before writing code, you need:
• A Medium Integration Token (found in your Medium account settings under Integration tokens).
• Your Medium User ID (retrieved via /v1/me).
• Endpoints for your target actions:
	• Create a Post: POST /v1/users/{authorId}/posts
	• Get Posts / Post details: GET /v1/users/{authorId}/posts or GET /v1/posts/{postId}
	• Update a Post: Medium’s API handles updates primarily via PUT /v1/posts/{postId} (note: Medium API supports updating post content/tags, though deleting posts via API has limitations or must be handled via profile/web interface depending on current Medium API scopes).

Step 2: Build the MCP Server

You can build a lightweight MCP server in Node.js or Python that wraps the Medium API endpoints into MCP tools (create_post, get_post, update_post, delete_post).
1. Set up your MCP server project (using @modelcontextprotocol/sdk for JS/TS or mcp for Python).
2. Define the tools:
	• medium_create_post: Accepts title, content, contentFormat (html or markdown), and publishStatus.
	• medium_get_post: Accepts a postId or lists user posts.
	• medium_update_post: Accepts a postId and fields to modify.
	• medium_delete_post: Deletes or unpublishes the post if supported by your implementation.
3. Pass the Medium Token either via environment variables on your server or via Claude's Request headers configuration (Authorization: Bearer YOUR_MEDIUM_TOKEN).

Step 3: Expose via a Tunnel (Local Development)

Because Claude cannot reach localhost directly, expose your local MCP server to the internet using a tunneling tool like ngrok or Cloudflare Tunnel:
bash
ngrok http 8000
Use code with caution.
Copy your public HTTPS forwarding URL (e.g., https://abc123.ngrok-free.app/mcp).

Step 4: Add the Custom Connector in Claude

1. Open Claude and navigate to Customize > Connectors (or Organization settings > Connectors).
2. Click the “+” button or Add > Custom > Web.
3. Enter a name (e.g., Medium Connector).
4. Paste your remote MCP server URL (e.g., https://abc123.ngrok-free.app/mcp).
5. Configure authentication:
	• Under Authentication, choose Sign in when needed or No sign in (if your server injects the token via Request headers).
	• Under Request headers, add your Medium API key/bearer token if your server expects Claude to pass it along.
6. Click Continue / Add to finish the setup