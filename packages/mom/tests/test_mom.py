"""Tests for probid mom (messaging/bot) package."""

import unittest

from probid_mom import BotStore, Conversation, Message, get_store


class MessageTests(unittest.TestCase):
    def test_message_defaults(self):
        msg = Message(role="user", content="hello")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "hello")
        self.assertIsNone(msg.timestamp)
        self.assertEqual(msg.metadata, {})

    def test_message_with_metadata(self):
        msg = Message(role="assistant", content="hi", metadata={"source": "slack"})
        self.assertEqual(msg.metadata["source"], "slack")


class ConversationTests(unittest.TestCase):
    def test_conversation_defaults(self):
        conv = Conversation(id="test-123")
        self.assertEqual(conv.id, "test-123")
        self.assertEqual(conv.messages, [])
        self.assertEqual(conv.context, {})

    def test_add_message(self):
        conv = Conversation(id="test")
        msg = conv.add_message("user", "hello")
        
        self.assertEqual(len(conv.messages), 1)
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "hello")

    def test_add_message_with_metadata(self):
        conv = Conversation(id="test")
        msg = conv.add_message("assistant", "hi there", {"channel": "slack"})
        
        self.assertEqual(msg.metadata["channel"], "slack")


class BotStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = BotStore()

    def test_create_and_get_conversation(self):
        conv = self.store.create_conversation("conv-1")
        self.assertEqual(conv.id, "conv-1")
        
        retrieved = self.store.get_conversation("conv-1")
        self.assertEqual(retrieved.id, "conv-1")

    def test_get_nonexistent_conversation(self):
        result = self.store.get_conversation("missing")
        self.assertIsNone(result)

    def test_list_conversations(self):
        self.store.create_conversation("a")
        self.store.create_conversation("b")
        
        self.assertEqual(sorted(self.store.list_conversations()), ["a", "b"])

    def test_delete_conversation(self):
        self.store.create_conversation("to-delete")
        
        result = self.store.delete_conversation("to-delete")
        self.assertTrue(result)
        self.assertIsNone(self.store.get_conversation("to-delete"))

    def test_delete_nonexistent_conversation(self):
        result = self.store.delete_conversation("missing")
        self.assertFalse(result)


class GlobalStoreTests(unittest.TestCase):
    def test_get_store_returns_same_instance(self):
        store1 = get_store()
        store2 = get_store()
        self.assertIs(store1, store2)


if __name__ == "__main__":
    unittest.main()
