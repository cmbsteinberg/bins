import asyncio
from pydantic_agent import create_agent


async def main(
    prompt="""Navigate to https://www.aberdeencity.gov.uk/services/bins-waste-and-recycling/check-bin-collection-days. Find out when the bins are taken for any address at Harvest Avenue. Return information on the bin timetable""",
):
    agent = create_agent()
    # Start MCP servers and run the agent
    async with agent.run_mcp_servers():
        # Example 1: Simple web scraping task
        result1 = await agent.run(prompt)
        print("Example 1 - Page Title:")
        print(result1.output)
        print("-" * 50)

        return result1


if __name__ == "__main__":
    prompt = """Navigate to https://www.aberdeencity.gov.uk/services/bins-waste-and-recycling/check-bin-collection-days. Find out when the bins are taken for any address at Harvest Avenue. Return information on the bin timetable"""
    asyncio.run(main())
