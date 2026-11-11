import asyncio
import logging
from typing import Any, Dict, Optional
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OllamaClusterRouter")

class Node:
    def __init__(self, name: str, url: str, priority: int):
        self.name = name
        self.url = url.rstrip("/")
        self.priority = priority  # Lower number = higher priority
        self.is_healthy = True
        self.consecutive_failures = 0

class OllamaClusterRouter:
    def __init__(self, nodes: list[Dict[str, Any]], max_queue_size: int = 100):
        self.nodes = [Node(**n) for n in sorted(nodes, key=lambda x: x["priority"])]
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.client = httpx.AsyncClient(timeout=60.0)
        self._running = False
        self._health_task: Optional[asyncio.Task] = None
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        self._health_task = asyncio.create_task(self._health_monitor_loop())
        self._worker_task = asyncio.create_task(self._request_worker_loop())
        logger.info("Cluster router initialized and running.")

    async def stop(self):
        self._running = False
        if self._health_task:
            self._health_task.cancel()
        if self._worker_task:
            self._worker_task.cancel()
        await self.client.aclose()
        logger.info("Cluster router stopped.")

    async def _check_node_health(self, node: Node) -> bool:
        try:
            response = await self.client.get(f"{node.url}/api/tags", timeout=3.0)
            if response.status_code == 200:
                node.consecutive_failures = 0
                return True
        except Exception:
            pass
        
        node.consecutive_failures += 1
        if node.consecutive_failures >= 3 and node.is_healthy:
            node.is_healthy = False
            logger.warning(f"Node marked UNHEALTHY: {node.name} ({node.url})")
        return False

    async def _health_monitor_loop(self):
        while self._running:
            for node in self.nodes:
                was_healthy = node.is_healthy
                is_healthy = await self._check_node_health(node)
                if not was_healthy and is_healthy:
                    node.is_healthy = True
                    logger.info(f"Node RECOVERED: {node.name} ({node.url})")
            await asyncio.sleep(5.0)

    def _get_active_node(self) -> Optional[Node]:
        for node in sorted(self.nodes, key=lambda x: x.priority):
            if node.is_healthy:
                return node
        return self.nodes[0] if self.nodes else None

    async def _request_worker_loop(self):
        while self._running:
            try:
                task_payload, future = await self.queue.get()
                node = self._get_active_node()
                
                if not node:
                    future.set_exception(RuntimeError("No available nodes in the cluster."))
                    self.queue.task_done()
                    continue

                success = False
                response_data = None
                
                for target_node in sorted(self.nodes, key=lambda x: x.priority):
                    try:
                        resp = await self.client.post(
                            f"{target_node.url}/api/generate",
                            json=task_payload,
                            timeout=120.0
                        )
                        if resp.status_code == 200:
                            response_data = resp.json()
                            success = True
                            break
                    except Exception as e:
                        logger.error(f"Failed execution on {target_node.name}: {e}")
                        target_node.is_healthy = False

                if success:
                    future.set_result(response_data)
                else:
                    future.set_exception(RuntimeError("All cluster nodes failed to process the request."))
                
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected worker error: {e}")

    async def submit_inference(self, payload: dict) -> dict:
        future = asyncio.get_running_loop().create_future()
        await self.queue.put((payload, future))
        return await future

async def main():
    nodes_config = [
        {"name": "Primary-Server", "url": "http://192.168.1.50:11434", "priority": 1},
        {"name": "Secondary-Server", "url": "http://192.168.1.51:11434", "priority": 2}
    ]

    router = OllamaClusterRouter(nodes_config)
    await router.start()

    payload = {
        "model": "llama3",
        "prompt": "Explain distributed systems in one sentence.",
        "stream": False
    }

    try:
        result = await router.submit_inference(payload)
        print("Inference Result:", result.get("response"))
    finally:
        await router.stop()

if __name__ == "__main__":
    asyncio.run(main())
