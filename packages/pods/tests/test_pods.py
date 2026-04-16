"""Tests for probid pods (model pod management) package."""

import unittest

from probid_pods import Pod, PodConfig, PodManager, get_manager


class PodTests(unittest.TestCase):
    def test_pod_defaults(self):
        pod = Pod(name="test-pod", model="gpt-4")
        self.assertEqual(pod.name, "test-pod")
        self.assertEqual(pod.model, "gpt-4")
        self.assertEqual(pod.status, "stopped")
        self.assertIsNone(pod.endpoint)

    def test_pod_with_config(self):
        pod = Pod(name="test", model="claude", status="running", endpoint="http://localhost:8080/test")
        self.assertEqual(pod.status, "running")
        self.assertEqual(pod.endpoint, "http://localhost:8080/test")


class PodConfigTests(unittest.TestCase):
    def test_pod_config_defaults(self):
        config = PodConfig(name="my-pod", model="gpt-4")
        self.assertEqual(config.name, "my-pod")
        self.assertEqual(config.model, "gpt-4")
        self.assertEqual(config.replicas, 1)

    def test_pod_config_with_resources(self):
        config = PodConfig(name="gpu-pod", model="gpt-4", gpu="A100", memory="32Gi", replicas=2)
        self.assertEqual(config.gpu, "A100")
        self.assertEqual(config.memory, "32Gi")
        self.assertEqual(config.replicas, 2)


class PodManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = PodManager()

    def test_create_pod(self):
        config = PodConfig(name="pod-1", model="gpt-4")
        pod = self.manager.create_pod(config)
        
        self.assertEqual(pod.name, "pod-1")
        self.assertEqual(pod.model, "gpt-4")

    def test_get_pod(self):
        self.manager.create_pod(PodConfig(name="pod-1", model="gpt-4"))
        
        pod = self.manager.get_pod("pod-1")
        self.assertIsNotNone(pod)
        self.assertEqual(pod.name, "pod-1")

    def test_get_nonexistent_pod(self):
        result = self.manager.get_pod("missing")
        self.assertIsNone(result)

    def test_list_pods(self):
        self.manager.create_pod(PodConfig(name="a", model="gpt-4"))
        self.manager.create_pod(PodConfig(name="b", model="claude"))
        
        pods = self.manager.list_pods()
        self.assertEqual(len(pods), 2)

    def test_start_pod(self):
        self.manager.create_pod(PodConfig(name="pod-1", model="gpt-4"))
        
        result = self.manager.start_pod("pod-1")
        
        self.assertTrue(result)
        pod = self.manager.get_pod("pod-1")
        self.assertEqual(pod.status, "running")
        self.assertIsNotNone(pod.endpoint)

    def test_start_nonexistent_pod(self):
        result = self.manager.start_pod("missing")
        self.assertFalse(result)

    def test_stop_pod(self):
        self.manager.create_pod(PodConfig(name="pod-1", model="gpt-4"))
        self.manager.start_pod("pod-1")
        
        result = self.manager.stop_pod("pod-1")
        
        self.assertTrue(result)
        pod = self.manager.get_pod("pod-1")
        self.assertEqual(pod.status, "stopped")
        self.assertIsNone(pod.endpoint)

    def test_delete_pod(self):
        self.manager.create_pod(PodConfig(name="pod-1", model="gpt-4"))
        
        result = self.manager.delete_pod("pod-1")
        
        self.assertTrue(result)
        self.assertIsNone(self.manager.get_pod("pod-1"))

    def test_delete_nonexistent_pod(self):
        result = self.manager.delete_pod("missing")
        self.assertFalse(result)


class GlobalManagerTests(unittest.TestCase):
    def test_get_manager_returns_same_instance(self):
        mgr1 = get_manager()
        mgr2 = get_manager()
        self.assertIs(mgr1, mgr2)


if __name__ == "__main__":
    unittest.main()
