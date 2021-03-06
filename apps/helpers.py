import requests

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import Http404
from django.utils.text import slugify

from apps.traditional.serializers import BookmarkListSerializer


class Client(object):
    URL = "https://api.itbook.store/1.0"

    def validate_response(self, response):
        if response.status_code != 200:
            raise Http404

    def byte_to_dict(self, response):
        from json import loads
        return loads(response.decode())

    def call(self, path, method, data):
        url = "%s/%s" % (self.URL, path)
        r = getattr(requests, method)(url, data)
        self.validate_response(r)
        return self.byte_to_dict(r.content)

    def search(self, q):
        return self.call('search/%s' % q, 'get', {})

    def book(self, isbn13):
        return self.call('books/%s' % isbn13, 'get', {})

    def books(self):
        return self.call('new', 'get', {})


class Adapter(object):

    def __init__(self):
        self.client = Client()

    def paginate(self, objects, page):
        paginator = Paginator(objects, settings.DEFAULT_PER_PAGE_LIMIT, page)
        return paginator.page(page)

    def search(self, q, page=1, paginated=True):
        key = 'search_%s' % slugify(q)
        books = self.get_from_cache(key)
        if not books:
            response = self.client.search(q)
            books = response['books']
            cache.set(key, books, settings.DEFAULT_CACHE_TIMEOUT)

        if paginated:
            books = self.paginate(books, page)
        return books

    def book(self, isbn13):
        key = 'book_%s' % isbn13
        book = self.get_from_cache(key)

        if not book:
            book = self.client.book(isbn13)
            cache.set(key, book, settings.DEFAULT_CACHE_TIMEOUT)

        return book

    def books(self, page=1, paginated=True):
        key = 'book_news'
        books = self.get_from_cache(key)

        if not books:
            response = self.client.books()
            books = response['books']
            cache.set(key, books, 60 * 60)

        if paginated:
            books = self.paginate(books, page)
        return books

    def get_from_cache(self, key):
        return cache.get(key)


def get_adapter():
    return Adapter()


def _generate_cache_key(app_name, user_id):
    return "%s_%s" % (app_name, user_id)


def _bookmarks(request):
    key = _generate_cache_key('bookmarks', request.user.id)

    bookmarks = cache.get(key)
    if not bookmarks:
        queryset = request.user.bookmark_set.all()
        serializer = BookmarkListSerializer(queryset)
        bookmarks = serializer.data
        cache.set(key, bookmarks, settings.DEFAULT_CACHE_TIMEOUT)

    page = request.GET.get('page', 1)
    paginator = Paginator(bookmarks, settings.DEFAULT_PER_PAGE_LIMIT, page)
    return paginator.page(page)

