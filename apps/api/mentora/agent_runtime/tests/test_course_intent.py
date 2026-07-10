"""course_intent 意图门控测试。"""

from django.test import SimpleTestCase

from mentora.agent_runtime.services.course_intent import (
    CourseChatIntent,
    classify_course_chat_intent,
)


class CourseIntentTests(SimpleTestCase):
    def test_smalltalk_disables_retrieval(self):
        for message in ("你好", "hello", "谢谢", "继续"):
            with self.subTest(message=message):
                access = classify_course_chat_intent(message)
                self.assertEqual(access.chat_intent, CourseChatIntent.SMALLTALK)
                self.assertFalse(access.allow_retrieval)
                self.assertTrue(access.allow_progress)

    def test_course_qa_enables_retrieval(self):
        for message in ("操作系统是什么", "解释这页内容", "总结当前资料"):
            with self.subTest(message=message):
                access = classify_course_chat_intent(message)
                self.assertEqual(access.chat_intent, CourseChatIntent.COURSE_QA)
                self.assertTrue(access.allow_retrieval)

    def test_progress_disables_retrieval(self):
        access = classify_course_chat_intent("下一步学什么")
        self.assertEqual(access.chat_intent, CourseChatIntent.PROGRESS)
        self.assertFalse(access.allow_retrieval)
        self.assertTrue(access.allow_progress)

    def test_mention_enables_retrieval(self):
        access = classify_course_chat_intent(
            "你好",
            mentions=[{"id": "sv-1", "type": "course_file", "label": "讲义"}],
        )
        self.assertEqual(access.chat_intent, CourseChatIntent.COURSE_QA)
        self.assertTrue(access.allow_retrieval)

    def test_reader_context_with_open_source(self):
        access = classify_course_chat_intent(
            "当前页在说什么",
            current_source_version_id="sv-1",
        )
        self.assertEqual(access.chat_intent, CourseChatIntent.READER_CONTEXT)
        self.assertTrue(access.allow_retrieval)

    def test_smalltalk_with_open_source_still_disables_retrieval(self):
        access = classify_course_chat_intent(
            "你好",
            current_source_version_id="sv-1",
        )
        self.assertEqual(access.chat_intent, CourseChatIntent.SMALLTALK)
        self.assertFalse(access.allow_retrieval)
