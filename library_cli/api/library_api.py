from .book import Book
from .user import User
from ..logger import Logger


class LibraryAPI(object):
    def __init__(self, client, logger: Logger):
        self.client = client
        self.logger = logger

    def log_tag(self, tag: str):
        """
        Update the tag of the logs.
        """
        self.logger.tag = tag

    def get_book(self, isbn: str) -> Book:
        """
        Get a Book with the given isbn from the library.

        :return: Book
        """
        raise NotImplementedError

    def add_book(self, book: Book) -> bool:
        """
        Add a Book to the library.

        :return: True if successful. False otherwise.
        """
        raise NotImplementedError

    def remove_book(self, book: Book) -> bool:
        """
        Remove a Book from the library.

        :return: True if successful. False otherwise.
        """
        raise NotImplementedError

    def get_user(self, username: str) -> User:
        """
        Get a User from the library.
        """
        raise NotImplementedError

    def add_user(self, user: User):
        """
        Add a User to the library.
        """
        raise NotImplementedError

    def remove_user(self, user: User):
        """
        Remove a User from the library.
        """
        raise NotImplementedError

    def check_out_book_for_user(self, book: Book, user: User):
        """
        Check out a Book for the User.
        """
        raise NotImplementedError

    def return_book_for_user(self, book: Book, user: User):
        """
        Return a book for the User.
        """
        raise NotImplementedError

    def get_user_stats(self, user: User):
        """
        Get the stats of the User.
        What books does the User currently have checked out and how many.
        """
        raise NotImplementedError

    def get_book_stats(self, book: Book):
        """
        Get the stats of the Book.
        Which user currently have this Book checked out.
        """
        raise NotImplementedError

    def success(self, format_string, *args):
        """
        Success level logging.
        """
        self.logger.success(format_string, *args)

    def info(self, format_string, *args):
        """
        Info level logging.
        """
        self.logger.info(format_string, *args)

    def warn(self, format_string, *args):
        """
        Warn level logging.
        """
        self.logger.warn(format_string, *args)

    def error(self, format_string, *args):
        """
        Error level logging.
        """
        self.logger.error(format_string, *args)
