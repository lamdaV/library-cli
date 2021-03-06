import click
from pymongo import MongoClient

from .mongo_api import MongoAPI
from ..command.action.action import action
from ..command.adder.adder import add
from ..command.deleter.deleter import delete
from ..command.editor.editor import edit
from ..command.remover.remover import remove
from ..command.searcher.searcher import search
from ..command.sorter.sorter import sort
from ..command.stat.stat import stat
from ..logger import Logger


@click.group()
@click.pass_context
def cli(context: click.Context):
    """
    Mongo Library Client Implementation.
    """
    logger = Logger()
    client = MongoClient()
    api = MongoAPI(client, logger)
    context.obj = {
        'api': api
    }


@cli.command()
@click.argument('arguments', nargs=-1, required=False)
def echo(arguments: tuple):
    """
    Echo arguments back.
    """
    click.secho(' '.join(arguments), fg='yellow')


cli.add_command(add)
cli.add_command(remove)
cli.add_command(edit)
cli.add_command(search)
cli.add_command(sort)
cli.add_command(action)
cli.add_command(stat)
cli.add_command(delete)
