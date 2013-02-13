# -*- coding: utf-8 -*-

import mock
import unittest2
from datetime import datetime, timedelta

import openerp
import openerp.tests.common as common
from openerp.addons.base_external_referentials.queue.job import (
        Job, OpenERPJobStorage, job,
        ENQUEUED, STARTED, DONE, FAILED)
from openerp.addons.base_external_referentials.session import (
        ConnectorSession)
from .common import mock_now


def task_b(session):
    pass


def task_a(session):
    pass


def dummy_task(session):
    return 'ok'


def dummy_task_args(session, a, b, c=None):
    return a + b + c


class test_job(unittest2.TestCase):
    """ Test Job """

    def setUp(self):
        self.session = mock.MagicMock()

    def test_new_job(self):
        """
        Create a job
        """
        job = Job(func=task_a)
        self.assertEqual(job.func, task_a)

    def test_priority(self):
        """ The lower the priority number, the higher
        the priority is"""
        job_a = Job(func=task_a, priority=10)
        job_b = Job(func=task_b, priority=5)
        self.assertGreater(job_a, job_b)

    def test_only_after(self):
        """ When an `only_after` datetime is defined, it should
        be executed after a job without one.
        """
        date = datetime.now() + timedelta(hours=3)
        job_a = Job(func=task_a, priority=10, only_after=date)
        job_b = Job(func=task_b, priority=10)
        self.assertGreater(job_a, job_b)

    def test_perform(self):
        job = Job(func=dummy_task)
        result = job.perform(self.session)
        self.assertEqual(result, 'ok')

    def test_perform_args(self):
        job = Job(func=dummy_task_args,
                  args=('o', 'k'),
                  kwargs={'c': '!'})
        result = job.perform(self.session)
        self.assertEqual(result, 'ok!')

class test_job_storage(common.TransactionCase):
    """ Test storage of jobs """

    def setUp(self):
        super(test_job_storage, self).setUp()
        self.pool = openerp.modules.registry.RegistryManager.get(common.DB)
        self.session = ConnectorSession(self.cr, self.uid)
        self.queue_job = self.registry('queue.job')

    def test_store(self):
        job = Job(func=task_a)
        storage = OpenERPJobStorage(self.session)
        storage.store(job)
        stored = self.queue_job.search(
                self.cr, self.uid,
                [('uuid', '=', job.uuid)])
        self.assertEqual(len(stored), 1)

    def test_read(self):
        only_after = datetime.now() + timedelta(hours=5)
        job = Job(func=dummy_task_args,
                  args=('o', 'k'),
                  kwargs={'c': '!'},
                  priority=15,
                  only_after=only_after)
        job.user_id = 1
        storage = OpenERPJobStorage(self.session)
        storage.store(job)
        job_read = storage.load(job.uuid)
        self.assertEqual(job.uuid, job_read.uuid)
        self.assertEqual(job.func, job_read.func)
        self.assertEqual(job.args, job_read.args)
        self.assertEqual(job.kwargs, job_read.kwargs)
        self.assertEqual(job.func_name, job_read.func_name)
        self.assertEqual(job.func_string, job_read.func_string)
        self.assertEqual(job.description, job_read.description)
        self.assertEqual(job.state, job_read.state)
        self.assertEqual(job.priority, job_read.priority)
        self.assertEqual(job.exc_info, job_read.exc_info)
        self.assertEqual(job.result, job_read.result)
        self.assertEqual(job.user_id, job_read.user_id)
        delta = timedelta(seconds=1)  # DB does not keep milliseconds
        self.assertAlmostEqual(job.date_created, job_read.date_created,
                               delta=delta)
        self.assertAlmostEqual(job.date_started, job_read.date_started,
                               delta=delta)
        self.assertAlmostEqual(job.date_enqueued, job_read.date_enqueued,
                               delta=delta)
        self.assertAlmostEqual(job.date_done, job_read.date_done,
                               delta=delta)
        self.assertAlmostEqual(job.only_after, job_read.only_after,
                               delta=delta)

    def test_job_delay(self):
        self.cr.execute('delete from queue_job')
        deco_task = job(task_a)
        task_a.delay(self.session)
        stored = self.queue_job.search(self.cr, self.uid, [])
        self.assertEqual(len(stored), 1)

    def test_job_delay_args(self):
        self.cr.execute('delete from queue_job')
        deco_task = job(dummy_task_args)
        task_a.delay(self.session, 'o', 'k', c='!')
        stored = self.queue_job.search(self.cr, self.uid, [])
        self.assertEqual(len(stored), 1)
