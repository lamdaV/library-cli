from typing import List

from neo4j.v1 import Driver, CypherError, StatementResult

from ..api.book import Book
from ..api.library_api import LibraryAPI
from ..api.user import User
from ..logger import Logger


class Neo4jAPI(LibraryAPI):
    def __init__(self, client: Driver, logger: Logger):
        super().__init__(client, logger)
        self.__setup()

    def __setup(self):
        self.client: Driver
        self.log_tag('INIT')

        with self.client.session() as session:
            self.info('setting up isbn uniqueness and existence constraint')
            statement = 'CREATE CONSTRAINT ON (book:Book) ASSERT (book.isbn) IS NODE KEY'
            session.run(statement)

            existence_constraints = ['title', 'pages', 'quantity']
            self.info('setting up existence constraints for book: {}', existence_constraints)
            for constraint in existence_constraints:
                statement = 'CREATE CONSTRAINT ON (book:Book) ASSERT EXISTS(book.{})'.format(constraint)
                session.run(statement)

            self.info('setting up username uniqueness and existence constraint')
            statement = 'CREATE CONSTRAINT ON (user:User) ASSERT (user.username) IS NODE KEY'
            session.run(statement)

            existence_constraints = ['phone', 'name']
            self.info('setting up existence constraints for user: {}', existence_constraints)
            for constraint in existence_constraints:
                statement = 'CREATE CONSTRAINT ON (user:User) ASSERT EXISTS(user.{})'.format(constraint)
                session.run(statement)

            self.info('setting up author name uniqueness and existence constraint')
            statement = 'CREATE CONSTRAINT ON (author:Author) ASSERT (author.name) IS NODE KEY'
            session.run(statement)

    def add_book(self, book: Book) -> bool:
        self.client: Driver
        self.info('adding {}', book)

        with self.client.session() as session:
            self.info('creating book {}', book)
            statement = '''
            CREATE (book:Book {isbn: {isbn}, title: {title}, pages: {pages}, quantity: {quantity}})
            RETURN book
            '''
            params = {
                'isbn': book.isbn,
                'title': book.title,
                'pages': book.pages,
                'quantity': book.quantity
            }

            if not self.__run_session(session, statement, params):
                return False

            self.info('linking authors {} to book', book.authors)
            for author in book.authors:
                if not self.__link_author_to_book(session, book.isbn, author):
                    return False

        self.success('added book {}', book)
        return True

    def add_user(self, user: User) -> bool:
        self.client: Driver
        self.info('adding {}', user)

        with self.client.session() as session:
            statement = '''
            CREATE (user:User {username: {username}, name: {name}, phone: {phone}})
            RETURN user
            '''
            params = {
                'username': user.username,
                'name': user.name,
                'phone': user.phone
            }
            if not self.__run_session(session, statement, params):
                return False
        self.success('added new user {}', user)
        return True

    def edit_book(self, isbn: str, field: str, value: List[str]) -> bool:
        self.Client: Driver
        self.info('editing book isbn={} field={} value={}', isbn, field, value)

        if field != 'authors' and len(value) > 1:
            self.error('field {} only accepts exactly 1 value but got {}', field, value)
            return False
        elif field != 'authors':
            value, *ignore = value

        if field == 'quantity' or field == 'pages':
            try:
                value = int(value)
            except ValueError:
                self.error('field {} requires value to be an integer but got {}', field, value)
                return False
            if value < 0:
                self.error('field {} requires value to be a positive integer by got {}', field, value)
                return False

        with self.client.session() as session:
            if field == 'authors':
                self.info('removing existing authors from book isbn={}', isbn)
                statement = '''
                MATCH (book:Book {isbn: {isbn}}) - [relationship:Author_Of] - (author:Author)
                DELETE relationship
                RETURN author
                '''
                params = {
                    'isbn': isbn
                }
                # NOTE: do not call __run_session if using result
                result = session.run(statement, params)

                self.info('cleaning up orphaned authors')
                for record in result.records():
                    author = record['author']
                    statement = '''
                    MATCH (author:Author {name: {name}}) - [relation:Author_Of] - (:Book)
                    RETURN COUNT(relation) as count
                    '''
                    params = {
                        'name': author.get('name')
                    }
                    result = session.run(statement, params)
                    for count_record in result.records():
                        if count_record['count'] == 0:
                            self.info('deleting author {} as there are no books with this author', author.get('name'))
                            statement = '''
                            MATCH (author:Author {name: {name}})
                            DELETE author
                            '''
                            if not self.__run_session(session, statement, params):
                                return False

                self.info('linking new authors {}', value)
                for author in value:
                    if not self.__link_author_to_book(session, isbn, author):
                        return False

            else:
                if field == 'quantity' or field == 'pages':
                    set_statement = 'SET book.{} = {} '.format(field, value)
                else:
                    set_statement = 'SET book.{} = "{}" '.format(field, value)
                statement = 'MATCH (book:Book {isbn: {isbn}}) ' + \
                            set_statement + \
                            'RETURN book'
                params = {
                    'isbn': isbn,
                    'field': field,
                    'value': value
                }
                if not self.__run_session(session, statement, params):
                    return False
        self.success('edited book with field={} and new value={}', field, value)
        return True

    def edit_user(self, username: str, field: str, value: str):
        self.client: Driver
        self.info('editing user username={} field={} value={}', username, field, value)

        if field == 'phone':
            try:
                value = int(value)
            except ValueError:
                self.error('field {} requires value to be an integer but got {}', field, value)
                return False

        with self.client.session() as session:
            if field == 'phone':
                set_statement = 'SET user.{} = {} '.format(field, value)
            else:
                set_statement = 'SET user.{} = "{}" '.format(field, value)
            statement = 'MATCH (user:User {username: {username}}) ' + \
                        set_statement + \
                        'RETURN user'
            params = {
                'username': username,
                'field': field,
                'value': value
            }
            if not self.__run_session(session, statement, params):
                return False
        self.success('edited book with field={} and new value={}', field, value)
        return True

    def find_book(self, field: str, value: any):
        self.client: Driver
        self.info('searching for book by field={} with value={}', field, value)

        with self.client.session() as session:
            if field == 'authors':
                statement = 'MATCH (book:Book) - [relation:Author_Of] - (author:Author)' + \
                            'WHERE author.name IN {}'.format(list(value)) + \
                            'RETURN book, author'
            elif len(value) == 1:
                value, *ignore = value
                statement = 'MATCH (book:Book {' + field + ': "' + value + '"}) - [relation:Author_Of] - (author:Author)' + \
                            'RETURN book, author'


            else:
                self.error('field {} only accepts exactly 1 value but got {}', field, value)
                return []

            try:
                result = session.run(statement)
                books = []
                for record in result.records():
                    books.append((record['book'], record['author']))
                return books
            except CypherError as e:
                self.error('{}', e.message)
                return []

    def find_user(self, field: str, value: str):
        self.client: Driver
        self.info('searching for user by field={} with value={}', field, value)

        with self.client.session() as session:
            if field == 'phone':
                # do not quote value. phone is an integer.
                match_statement = 'MATCH (user:User {' + field + ': ' + value + '}) '
            else:
                # quote the value
                match_statement = 'MATCH (user:User {' + field + ': "' + value + '"}) '

            statement = match_statement + \
                        'RETURN user'
            try:
                result = session.run(statement)
                users = []
                for record in result.records():
                    users.append(record['user'])
                return users
            except CypherError as e:
                self.error('{}', e.message)
                return []

    def sort_book_by(self, field: str):
        self.client: Driver
        self.info('sorting book by field={}', field)

        if field == 'authors':
            order_by_statement = 'ORDER BY author.name'
        else:
            order_by_statement = 'ORDER BY book.{}'.format(field)

        with self.client.session() as session:
            statement = 'MATCH (book:Book) - [relation:Author_Of] - (author:Author) ' + \
                        'RETURN book, author ' + \
                        order_by_statement
            try:
                result = session.run(statement)
                books = []
                for record in result.records():
                    books.append((record['book'], record['author']))
                return books
            except CypherError as e:
                self.error('{}', e.message)
                return []

    def sort_user_by(self, field: str):
        self.client: Driver
        self.info('sorting user by field={}', field)

        with self.client.session() as session:
            statement = 'MATCH (user:User) ' + \
                        'RETURN user ' + \
                        'ORDER BY user.{}'.format(field)
            try:
                result = session.run(statement)
                users = []
                for record in result.records():
                    users.append(record['user'])

                return users
            except CypherError as e:
                self.error('{}', e.message)
                return []

    def check_out_book_for_user(self, isbn: str, username: str):
        self.client: Driver
        self.info('check out book isbn={} for user username={}', isbn, username)

        try:
            # Check if book exists
            self.info('verifying book exists')
            book_result = self.get_book(isbn)
            book = None
            quantity = 0
            for book_record in book_result.records():
                book = book_record['book']
                quantity = book.get('quantity')
            if not book:
                self.error('book isbn={} does not exist', isbn)
                return False

            # Verify book has stock
            self.info('verifying book is in stock')
            if quantity <= 0:
                self.error('book isbn={} is out of stock', isbn)
                return False

            # Check if user exists
            self.info('verifying user exists')
            user_result = self.get_user(username)
            user = None
            for user_record in user_result.records():
                user = user_record['user']
            if not user:
                self.error('user username={} does not exist', username)
                return False

            with self.client.session() as session:
                self.info('merging borrows relation')
                statement = '''
                MATCH (user:User {username: {username}})
                MATCH (book:Book {isbn: {isbn}})
                MERGE (user) - [borrows:Borrows] -> (book)
                ON CREATE SET borrows.quantity = 1
                ON MATCH SET borrows.quantity = borrows.quantity + 1
                RETURN borrows
                '''
                params = {
                    'username': username,
                    'isbn': isbn
                }
                result = session.run(statement, params)
                self.__log_result(result)

                self.info('decrementing book stock')
                statement = 'MATCH (book:Book {isbn: {isbn}}) ' + \
                            'SET book.quantity = book.quantity - 1 ' + \
                            'RETURN book'
                params = {
                    'isbn': isbn
                }
                result = session.run(statement, params)
                self.__log_result(result)

                self.success('checked out book isbn={} for user username={}', isbn, username)
                return True
        except CypherError as e:
            return self.__handle_cyphererror(e)

    def return_book_for_user(self, isbn: str, username: str):
        self.client: Driver
        self.info('return book isbn={} for user username={}', isbn, username)

        try:
            with self.client.session() as session:
                self.info('retrieving borrows relation')
                statement = '''
                MATCH (user:User {username: {username}})  - [borrows:Borrows] - (book:Book {isbn: {isbn}})
                RETURN borrows
                '''
                params = {
                    'isbn': isbn,
                    'username': username
                }
                result = session.run(statement, params)
                borrows = None
                for record in result.records():
                    borrows = record['borrows']

                self.info('verifying borrows relation exists')
                if not borrows:
                    self.error('book isbn={} was not checked out by user username={}', isbn, username)
                    return False

                quantity = borrows.get('quantity')
                if quantity == 1:
                    self.info('deleting borrows relation: all books isbn={} returned', isbn)
                    statement = '''
                    MATCH (user:User {username: {username}})  - [borrows:Borrows] - (book:Book {isbn: {isbn}}) 
                    DELETE borrows 
                    SET book.quantity = book.quantity + 1
                    RETURN book
                    '''
                else:
                    self.info('decrementing borrows relation quantity')
                    statement = '''
                    MATCH (user:User {username: {username}})  - [borrows:Borrows] - (book:Book {isbn: {isbn}}) 
                    SET borrows.quantity = borrows.quantity - 1, book.quantity = book.quantity + 1 
                    RETURN book
                    '''
                result = session.run(statement, params)

                self.__log_result(result)

                self.success('returned book isbn={} for user username={}', isbn, username)
                return True
        except CypherError as e:
            return self.__handle_cyphererror(e)

    def get_book_stats(self, isbn: str):
        self.client: Driver
        self.info('retrieving users borrowing book isbn={}', isbn)

        with self.client.session() as session:
            self.info('verifying book exists')
            book = None
            book_result = self.get_book(isbn)
            for book_record in book_result.records():
                book = book_record['book']
            if not book:
                self.error('book isbn={} does not exist', isbn)
                return False

            statement = '''
            MATCH (book:Book {isbn: {isbn}}) - [borrows:Borrows] - (user:User)
            RETURN user, borrows
            '''
            params = {
                'isbn': isbn
            }
            try:
                result = session.run(statement, params)
                users = []
                for record in result.records():
                    users.append((record['user'], record['borrows']))
                return users
            except CypherError as e:
                return self.__handle_cyphererror(e)

    def get_user_stats(self, username: str):
        self.client: Driver
        self.info('retrieving books borrowed by user username={}', username)

        with self.client.session() as session:
            self.info('verifying book exists')
            user = None
            user_result = self.get_user(username)
            for user_record in user_result.records():
                user = user_record['user']
            if not user:
                self.error('user username={} does not exist', username)
                return []

            statement = '''
            MATCH (user:User {username: {username}}) - [borrows:Borrows] - (book:Book)
            RETURN book, borrows
            '''
            params = {
                'username': username
            }
            try:
                result = session.run(statement, params)
                books = []
                for record in result.records():
                    books.append((record['book'], record['borrows']))
                return books
            except CypherError as e:
                return self.__handle_cyphererror(e)

    def rate_book(self, username: str, isbn: str, score: int):
        self.client: Driver

        try:
            self.info('verifying user exists')
            user_result = self.get_user(username)
            user = None
            for user_record in user_result.records():
                user = user_record['user']
            if not user:
                self.error('user username={} does not exist', username)
                return False

            self.info('verifying book exists')
            book_result = self.get_book(isbn)
            book = None
            for book_record in book_result.records():
                book = book_record['book']
            if not book:
                self.error('book isbn={} does not exist', isbn)
                return False

            with self.client.session() as session:
                self.info('verifying rating does not exists')
                statement = '''
                MATCH (user:User {username: {username}}) - [rates:Rates] - (book:Book {isbn: {isbn}})
                RETURN rates
                '''
                params = {
                    'username': username,
                    'isbn': isbn
                }
                result = session.run(statement, params)
                for record in result.records():
                    if 'rates' in record.keys():
                        rates = record['rates']
                        self.error('user username={} has already rated book isbn={} with score={}', username, isbn,
                                   rates.get('score'))
                        return False

                create_statement = 'CREATE (user) - [rates:Rates {score: ' + str(score) + '}] -> (book)'
                statement = 'MATCH (user:User {username: {username}}) ' + \
                            'MATCH (book:Book {isbn: {isbn}}) ' + \
                            create_statement
                if not self.__run_session(session, statement, params):
                    return False
            self.success('added rating score={} by user username={} to book isbn={}', score, username, isbn)
            return True
        except CypherError as e:
            return self.__handle_cyphererror(e)

    def recommend_books(self, username: str):
        self.client: Driver
        self.info('getting recommendations for user username={}', username)

        with self.client.session() as session:
            statement = '''
            MATCH (:User {username: {username}}) - [r1:Rates] - (b1:Book) - [r2:Rates] - (friend:User) - [r3:Rates] - (b2:Book)
            WHERE r1.score = r2.score
                AND r3.score >= 3
            RETURN b2 as recommendation
            '''
            params = {
                'username': username
            }
            try:
                result = session.run(statement, params)
                recommendations = []
                for record in result.records():
                    recommendations.append(record['recommendation'])
                return recommendations
            except CypherError as e:
                self.__handle_cyphererror(e)
                return []

    def remove_book(self, isbn: str):
        self.client: Driver
        self.info('removing book isbn={}', isbn)

        with self.client.session() as session:
            try:
                self.info('checking book user relations')
                statement = '''
                MATCH (book:Book {isbn: {isbn}}) - [r] - (:User)
                RETURN COUNT(r) as relations
                '''
                book_params = {
                    'isbn': isbn
                }
                result = session.run(statement, book_params)
                relation_count = 1
                for record in result.records():
                    relation_count = record['relations']
                if relation_count != 0:
                    self.error('book isbn={} is involved in {} user relations', isbn, relation_count)
                    return False

                self.info('removing for all author_of relations')
                statement = '''
                MATCH (book:Book {isbn: {isbn}}) - [relation:Author_Of] - (author:Author)
                DELETE relation
                RETURN author
                '''
                result = session.run(statement, book_params)

                self.info('checking for orphaned authors')
                for record in result.records():
                    author = record['author']
                    name = author.get('name')
                    statement = '''
                    MATCH (author:Author {name: {name}})
                    MATCH (author) - [relation:Author_Of] - (book:Book)
                    RETURN COUNT(relation) as relations
                    '''
                    author_params = {
                        'name': name
                    }
                    author_result = session.run(statement, author_params)
                    for author_record in author_result.records():
                        relation_count = author_record['relations']
                        if relation_count == 0:
                            self.info('deleting author name={}', author.get('name'))
                            statement = '''
                            MATCH (author:Author {name: {name}})
                            DELETE author
                            '''

                            if not self.__run_session(session, statement, author_params):
                                self.error('failed to delete author name={}', name)
                                return False

                self.info('removing book isbn={}', isbn)
                statement = '''
                MATCH (book:Book {isbn: {isbn}})
                DELETE book
                '''
                book_params = {
                    'isbn': isbn
                }
                if self.__run_session(session, statement, book_params):
                    self.success('removed book isbn={}', isbn)
                    return True
                return False
            except CypherError as e:
                return self.__handle_cyphererror(e)

    def remove_user(self, username: str):
        """
        check if user exists
        check if user made a review or is borrowing a book
        delete user
        """
        self.client: Driver

        with self.client.session() as session:
            try:
                statement = '''
                MATCH (user:User {username: {username}}) - [r] - (:Book)
                RETURN COUNT(r) as relations
                '''
                params = {
                    'username': username
                }
                result = session.run(statement, params)

                for record in result.records():
                    book_relations = record['relations']
                    if book_relations != 0:
                        self.error('user username={} is involved in {} book relations', username, book_relations)
                        return False

                statement = '''
                MATCH (user:User {username: {username}})
                DELETE user
                '''
                session.run(statement, params)
                self.success('removed user username={}', username)
                return True
            except CypherError as e:
                return self.__handle_cyphererror(e)

    def get_book(self, isbn: str):
        self.client: Driver

        with self.client.session() as session:
            statement = '''
            MATCH (book:Book {isbn: {isbn}})
            RETURN book
            '''
            params = {
                'isbn': isbn
            }
            return session.run(statement, params)

    def get_user(self, username: str):
        self.client: Driver
        self.info('removing user username={}', username)

        with self.client.session() as session:
            self.info('checking book relations')
            statement = '''
            MATCH (user:User {username: {username}})
            RETURN user
            '''
            params = {
                'username': username
            }
            return session.run(statement, params)

    def __link_author_to_book(self, session, isbn, name):
        statement = '''
        MATCH(book: Book {isbn: {isbn}})
        MERGE(author: Author {name: {name}})
        CREATE(book) <- [relation: Author_Of] - (author)
        RETURN author
        '''
        params = {
            'isbn': isbn,
            'name': name
        }
        return self.__run_session(session, statement, params)

    def __run_session(self, session, statement, params):
        try:
            result = session.run(statement, params)
            self.__log_result(result)
            return True
        except CypherError as e:
            return self.__handle_cyphererror(e)

    def __handle_cyphererror(self, error: CypherError):
        self.error('{}', error.message)
        return False

    def __log_result(self, result: StatementResult):
        for record in result.records():
            for key in record.keys():
                self.info('{}: {}', key, record[key])
