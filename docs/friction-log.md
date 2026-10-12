# Friction log

Things that slowed the build down, in the order they happened. Add your own Amazon-specific notes below.

## MCP Python SDK (`mcp` 2.3.0)
- **`FastMCP` is gone.** Most examples I knew import `mcp.server.fastmcp.FastMCP`. In 2.x it is `mcp.server.mcpserver.MCPServer`. The import error names the rename and links a migration guide, which helped; a deprecation shim would have helped more.
- **Docs were not reachable from my build environment**, so I read the installed package source (`inspect.signature`, `run`, `custom_route`) instead. That worked but cost time.
- **DNS-rebinding protection** rejects any `Host` that is not `localhost:*` by default. Correct for safety, but my first test failed with a bare "Invalid Host header" log line and no hint in the HTTP response. Hosted deployments need this configured explicitly.

## Alexa+ developer tools
- The hackathon FAQ states the MCP Toolkit, CLI and Web Simulator are available to select partners only, with no way for participants to apply. I could not test against real Alexa+, so the demo uses a web page acting as an MCP client.
- Constraints I could only read about, not test: Streamable HTTP required, OAuth 2.x only (no dynamic client registration), 500 ms latency target, US availability.

## Add your notes here
- (what you used it for / what worked / what needs work / how getting started went / would you build with it again, yes or no and why)
