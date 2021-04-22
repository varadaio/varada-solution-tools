from json import dumps
from typing import Tuple
from .constants import Paths
from logbook import DEBUG, INFO
from .configuration import get_config
from .rest_commands import RestCommands
from click import group, argument, option, echo
from .utils import read_file_as_json, logger
from .remote import parallel_download, parallel_ssh_execute, rest_execute, ssh_session
from .connections import PrestoRest


@option("-v", "--verbose", is_flag=True, default=False)
@group()
def main(verbose):
    """
    Varada trino manager
    """
    logger.level = DEBUG if verbose else INFO


@main.group()
def ssh():
    """
    SSH related operations
    """
    pass


@argument("node", default="coordinator", nargs=1)
@ssh.command()
def connect(node):
    """
    Start ssh session with one of the nodes, example: coordinator/node-1,node-2
    """
    ssh_session(node=node)


@argument("command", nargs=-1)
@ssh.command()
def command(command: Tuple[str]):
    """
    Send command via SSH to all nodes
    """
    for task, hostname in parallel_ssh_execute(" ".join(command)):
        echo(f"{hostname}: {task.result()}")


@main.group()
def etc():
    """
    More utilities
    """
    pass


@etc.command()
def is_panic():
    """
    Verify if a node is in panic
    """
    command = "tail -n 30 /var/log/presto/launcher.log | grep -i panic | wc -l"
    tasks = parallel_ssh_execute(command=command)
    for panic, hostname in tasks:
        if bool(int(panic.result().strip())):
            echo(f"found panic in {hostname}")


@main.group()
def server():
    """
    Server management related commands
    """
    pass


@server.command()
def stop():
    """
    Start presto service
    """
    parallel_ssh_execute(command="sudo systemctl stop presto")


@server.command()
def start():
    """
    Start presto service
    """
    parallel_ssh_execute(command="sudo systemctl start presto")


@server.command()
def restart():
    """
    Restart presto service
    """
    parallel_ssh_execute(command="sudo systemctl restart presto")


@server.command()
def status():
    """
    Checks if the cluster is successfully running
    """
    con = get_config().get_connection_by_name("coordinator")
    echo(rest_execute(con=con, rest_client_type=PrestoRest, func=RestCommands.status))


@main.group()
def logs():
    """
    Logs related commands
    """
    pass


@logs.command()
def clear():
    """
    Clear logs
    """
    parallel_ssh_execute(command="rm /var/log/presto/*")


@logs.command()
def collect():
    """
    Collect fresh logs and store in logs dir, overwiting existing one
    """
    commands = [
        "sudo rm -rf /tmp/custom_logs",
        "mkdir /tmp/custom_logs",
        "sudo dmesg > /tmp/custom_logs/dmesg",
        "sudo jps > /tmp/custom_logs/jps",
        'grep TrinoServer /tmp/custom_logs/jps | cut -d" " -f1 > /tmp/custom_logs/server.pid || true',
        "sudo jstack $(cat /tmp/custom_logs/server.pid) > /tmp/custom_logs/jstack.txt || true",
        "sudo pstack $(cat /tmp/custom_logs/server.pid) > /tmp/custom_logs/pstack.txt || true",
        "cp /var/log/presto/* /tmp/custom_logs/ || true",
        "sudo cp /var/log/messages /tmp/custom_logs/",
        "sudo cp /var/log/user-data.log /tmp/custom_logs/",
        "sudo tar -C /tmp/custom_logs -zcf /tmp/custom_logs.tar.gz .",
        "sudo chmod 777 /tmp/custom_logs.tar.gz",
    ]
    parallel_ssh_execute(command="\n".join(commands))
    parallel_download(
        remote_file_path="/tmp/custom_logs.tar.gz", local_dir_path=Paths.logs_path
    )


@main.group()
def rules():
    """
    Rules utility commands
    """


@rules.command()
def generate():
    """
    Generate rule
    """
    pass


@rules.command()
def apply():
    """
    Apply rule to the cluster
    """
    pass


@rules.command()
def get():
    """
    Get rule from the cluster
    """
    pass


@rules.command()
def delete():
    """
    Delete rule from the cluster
    """
    pass


@main.group()
def config():
    """
    Config related commands
    """
    pass


@config.command()
def show():
    data = read_file_as_json(Paths.config_path)
    echo(dumps(data, indent=2))


@config.command()
def example():
    data = {
        "coordinator": "coordinator.example.com",
        "workers": [
            "worker1.example.com",
            "worker2.example.com",
            "worker3.example.com",
        ],
        "port": 22,
        "username": "root",
    }
    echo(f'Simple:\n{dumps(data, indent=2)}')
    echo('') # new line
    data["bastion"] = {
        "hostname": "bastion.example.com",
        "port": 22,
        "username": "root",
    }
    echo(f'With bastion:\n{dumps(data, indent=2)}')


if __name__ == "__main__":
    main()
