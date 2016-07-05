# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import mock
import pytest

import structlog
from pyramid import testing
from testscaffold.tests.utils import tmp_session_context, session_context

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


def dummy_request(dbsession):
    from webob.multidict import MultiDict
    from pyramid.request import apply_request_extensions

    req = testing.DummyRequest(base_url='http://testscaffold.com',
                               dbsession=dbsession)
    req.route_url = mock.Mock(return_value='/')
    req.POST = MultiDict()
    req.GET = MultiDict()
    req.params = MultiDict()
    req.session = mock.Mock()
    apply_request_extensions(req)
    return req


@pytest.mark.usefixtures('with_migrations', 'clean_tables', 'minimal_setup')
class TestFixtureCleanup(object):
    def test_cleanup(self, sqla_session):
        from testscaffold.models.user import User
        with session_context(sqla_session) as session:
            user = User(id=1, email='foasfsfao', user_name='barafsf')
            user.persist(flush=True, db_session=session)


@pytest.mark.usefixtures('with_migrations', 'clean_tables_once',
                         'minimal_setup')
class TestUsersAPI(object):
    def test_wrong_post(self, sqla_session):
        from testscaffold.views.api.users import UserAPIView
        import marshmallow
        with tmp_session_context(sqla_session) as session:
            request = dummy_request(session)
            request.json_body = {}
            with pytest.raises(marshmallow.ValidationError):
                UserAPIView(request).post()

    def test_proper_post(self, sqla_session):
        from testscaffold.views.api.users import UserAPIView
        with tmp_session_context(sqla_session) as session:
            request = dummy_request(session)
            request.json_body = {
                'user_name': 'new_user',
                'email': 'foo@bar.baz',
                'password': 'dupa'
            }
            result = UserAPIView(request).post()
            result_json = result.__json__(request)
            assert result_json['id'] > 0
            assert result_json['user_name'] == 'new_user'
            assert result_json['email'] == 'foo@bar.baz'
            assert 'password' not in result_json

    def test_get_not_found(self, sqla_session):
        from testscaffold.views.api.users import UserAPIView
        import pyramid.httpexceptions
        with tmp_session_context(sqla_session) as session:
            request = dummy_request(session)
            request.matchdict['object_id'] = -5
            with pytest.raises(pyramid.httpexceptions.HTTPNotFound):
                UserAPIView(request).get()

    def test_get_found(self, sqla_session):
        from testscaffold.views.api.users import UserAPIView
        from testscaffold.models.user import User
        with tmp_session_context(sqla_session) as session:
            request = dummy_request(session)
            user = User(id=5, email='foo', user_name='bar')
            user.persist(flush=True, db_session=request.dbsession)
            request.matchdict['object_id'] = 5
            result = UserAPIView(request).get()
            assert result.id == 5

    def test_patch_not_found(self, sqla_session):
        from testscaffold.views.api.users import UserAPIView
        import pyramid.httpexceptions
        with tmp_session_context(sqla_session) as session:
            request = dummy_request(session)
            request.matchdict['object_id'] = 1
            with pytest.raises(pyramid.httpexceptions.HTTPNotFound):
                UserAPIView(request).patch()

    def test_patch_found_invalid(self, sqla_session):
        import marshmallow
        from testscaffold.views.api.users import UserAPIView
        from testscaffold.models.user import User
        with tmp_session_context(sqla_session) as session:
            request = dummy_request(session)
            user = User(id=1, email='foo', user_name='bar')
            user.persist(flush=True, db_session=request.dbsession)
            request.matchdict['object_id'] = 1
            request.json_body = {}
            with pytest.raises(marshmallow.ValidationError):
                UserAPIView(request).patch()

    def test_patch_found_valid(self, sqla_session):
        from testscaffold.views.api.users import UserAPIView
        from testscaffold.models.user import User
        with tmp_session_context(sqla_session) as session:
            request = dummy_request(session)

            request.json_body = {
                'user_name': 'changed',
                'email': 'bar@foo.com',
            }

            user = User(id=1, email='foo', user_name='bar')
            user.persist(flush=True, db_session=request.dbsession)
            request.matchdict['object_id'] = 1
            result = UserAPIView(request).patch()
            assert result.user_name == 'changed'
            assert result.email == 'bar@foo.com'
