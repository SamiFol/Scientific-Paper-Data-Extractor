import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Listează tool-urile disponibile
            tools = await session.list_tools()
            print("🔧 Tool-uri disponibile:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Apelează tool-ul de test
            print("\n🚀 Apelez generate_sample_paper...")
            result = await session.call_tool("generate_sample_paper", {})
            print(f"✅ Rezultat: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(main())