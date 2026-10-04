import asyncio
import sys
from pathlib import Path

import httpx
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import core

URL = "https://ash-speed.hetzner.com/100MB.bin"
REQUESTS = 10
TIMEOUT = 60.0

HEADERS = {
    "Accept-Encoding": "identity",
    "Cache-Control": "no-cache, no-store",
}

console = Console()


def show_progress(number, elapsed, size):
    if size is None:
        console.print(f"  [red]#{number}[/red]  [red]ошибка: {elapsed}[/red]")
        return
    speed = (size / core.MB) / elapsed
    console.print(
        f"  [dim]#{number:<3}[/dim] {elapsed:7.3f} с  {size:>13,} байт  "
        f"[bold green]{speed:6.2f} МБ/с[/bold green]  {speed * 8:6.1f} Мбит/с"
    )


def requests_table(report):
    table = Table(title="Запросы", title_style="bold cyan", expand=False, padding=(0, 1))
    table.add_column("#", justify="right", style="dim")
    table.add_column("байты", justify="right")
    table.add_column("время, с", justify="right")
    table.add_column("МБ/с", justify="right")
    table.add_column("Мбит/с", justify="right")
    for i, (elapsed, size) in enumerate(zip(report["times"], report["sizes"]), start=1):
        speed = (size / core.MB) / elapsed
        table.add_row(
            str(i), f"{size:,}".replace(",", " "), f"{elapsed:.3f}",
            f"{speed:.2f}", f"{speed * 8:.1f}",
        )
    return table


def summary_table(report):
    t, s = report["time"], report["speed"]
    average = report["average_mbps"]

    table = Table(title="Итог", title_style="bold cyan", expand=False, padding=(0, 1))
    table.add_column("Метрика")
    table.add_column("Значение", justify="right")

    table.add_row("запросов выполнено", f"{len(report['times'])} из {report['requests']}")
    table.add_row(
        Text("среднее время запроса", style="bold"), Text(f"{t['expected']:.3f} с", style="bold")
    )
    table.add_row("  стандартное отклонение", f"{t['std']:.3f} с")
    table.add_row("  мин / макс", f"{t['min']:.3f} / {t['max']:.3f} с")
    table.add_row("", "")
    table.add_row(
        Text("средняя скорость", style="bold"),
        Text(f"{average:.2f} МБ/с ({average * 8:.1f} Мбит/с)", style="bold green"),
    )
    table.add_row("  M(ξ) по запросам", f"{s['expected']:.2f} МБ/с")
    table.add_row("  s(ξ) по запросам", f"{s['std']:.2f} МБ/с")
    table.add_row("  мин / макс", f"{s['min']:.2f} / {s['max']:.2f} МБ/с")
    table.add_row("", "")
    table.add_row("всего скачано", f"{report['total_mb']:.1f} МБ за {report['wall_time']:.2f} с")
    return table


def failures_panel(report):
    lines = [Text(f"#{n}: {e}", style="red") for n, e in report["failures"]]
    return Panel(Group(*lines), title="Не удались запросы", border_style="red")


def print_report(report):
    if not report["times"]:
        console.print(failures_panel(report))
        return

    console.print(requests_table(report))
    console.print(summary_table(report))
    if report["failures"]:
        console.print(failures_panel(report))


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else URL

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        task = progress.add_task(f"качаем {url}", total=REQUESTS)

        def report_progress(number, elapsed, size):
            if size is not None:
                progress.advance(task)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(TIMEOUT, connect=10.0), headers=HEADERS
        ) as client:
            report = await core.measure(
                url, client, requests=REQUESTS, on_result=report_progress
            )

    show_progress_bulk(report)
    print_report(report)
    return 0 if report["times"] else 1


def show_progress_bulk(report):
    for i, (elapsed, size) in enumerate(zip(report["times"], report["sizes"]), start=1):
        show_progress(i, elapsed, size)
    for number, error in report["failures"]:
        show_progress(number, error, None)
    console.print()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
