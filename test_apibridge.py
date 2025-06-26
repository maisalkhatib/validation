import asyncio
import aiohttp
import json

async def test_api_bridge():
    async with aiohttp.ClientSession() as session:
        # Test health
        async with session.get('http://localhost:8000/health') as resp:
            print(f"Health: {await resp.json()}")
        
        # Test inventory status
        async with session.post('http://localhost:8000/api/inventory/refill') as resp:
            print(f"Inventory: {json.dumps(await resp.json(), indent=2)}")
        
        # Test refill
        # async with session.post(
        #     'http://localhost:8000/api/inventory/refill',
        #     json={"ingredient": "milk"}
        # ) as resp:
        #     print(f"Refill: {await resp.json()}")

if __name__ == "__main__":
    asyncio.run(test_api_bridge())