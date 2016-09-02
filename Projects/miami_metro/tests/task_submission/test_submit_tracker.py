from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
from platformdatafetcher.platformutils import TaskSubmissionTracker


class TestSubmissionTracker(unittest.TestCase):
    def test_flat_context(self):
        tracker = TaskSubmissionTracker()
        with tracker.total():
            with tracker.operation("submit_one"):
                pass

            with tracker.operation("submit_two"):
                pass

        self.assertEqual('Total', tracker.root_context.name)
        self.assertEqual(['submit_one', 'submit_two'], [c.name for c in tracker.root_context.children])

    def test_nested_contexts(self):
        tracker = TaskSubmissionTracker()
        with tracker.total():
            with tracker.operation("submit_one"):
                with tracker.operation("submit_two"):
                    pass
                with tracker.operation("submit_three"):
                    pass
            with tracker.operation('submit_more'):
                pass

        self.assertEqual('Total', tracker.root_context.name)
        self.assertEqual(['submit_one', 'submit_more'], [c.name for c in tracker.root_context.children])
        self.assertEqual(['submit_two', 'submit_three'], [c.name for c in tracker.root_context.children[0].children])

    def test_report(self):
        tracker = TaskSubmissionTracker()
        with tracker.total():
            with tracker.operation("submit_one"):
                with tracker.operation("submit_two"):
                    pass

        expected_report = '''
Total: 0.00 s
-submit_one: 0.00 s
--submit_two: 0.00 s
'''.strip()
        self.assertIn(expected_report, tracker.generate_report())


    def test_task_counts(self):
        tracker = TaskSubmissionTracker()
        with tracker.total():
            for i in range(3):
                tracker.count_task("task_one")
            tracker.count_task("task_two")
            for i in range(3):
                tracker.count_task("fetch.Twitter")
            for i in range(3):
                tracker.count_task("fetch.Blogspot")

        expected_report = '''
fetch.Blogspot: 3
fetch.Twitter: 3
task_one: 3
task_two: 1
'''.strip()

        self.assertIn(expected_report, tracker.generate_report())
