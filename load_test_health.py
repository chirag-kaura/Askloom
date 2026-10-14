
import asyncio
import time
import aiohttp

URL = "http://127.0.0.1:8000/health"
TOTAL_REQUESTS = 50
CONCURRENCY_LEVELS = [1, 5, 10, 20]


async def make_request(session):
    start = time.perf_counter()

    try:
        async with session.get(URL) as response:
            await response.read()
            latency = time.perf_counter() - start
            return latency, response.status == 200
    except Exception:
        return time.perf_counter() - start, False


async def run_test(concurrency):
    connector = aiohttp.TCPConnector(limit=concurrency)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout
    ) as session:
        start = time.perf_counter()

        results = await asyncio.gather(
            *[
                make_request(session)
                for _ in range(TOTAL_REQUESTS)
            ]
        )

        duration = time.perf_counter() - start

    latencies = sorted(latency for latency, _ in results)
    successes = sum(success for _, success in results)
    failures = TOTAL_REQUESTS - successes
    p95_index = max(0, int(0.95 * len(latencies)) - 1)

    print(f"\nConcurrency: {concurrency}")
    print(f"Total requests: {TOTAL_REQUESTS}")
    print(f"Successful: {successes}")
    print(f"Failed: {failures}")
    print(f"Average latency: {sum(latencies) / len(latencies) * 1000:.2f} ms")
    print(f"P95 latency: {latencies[p95_index] * 1000:.2f} ms")
    print(f"Maximum latency: {max(latencies) * 1000:.2f} ms")
    print(f"Throughput: {TOTAL_REQUESTS / duration:.2f} requests/sec")


async def main():
    for concurrency in CONCURRENCY_LEVELS:
        await run_test(concurrency)


if __name__ == "__main__":
    asyncio.run(main())
