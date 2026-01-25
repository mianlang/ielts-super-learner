"""Main CLI entry point for IELTS Agent."""

import sys
import argparse
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings

from ielts_agent.config import SKILLS
from ielts_agent.db import init_db, get_or_create_user, create_session, end_session, save_interaction, update_progress, get_progress, get_user_stats, get_recent_sessions
from ielts_agent.agents import TutorAgent, PracticeAgent, ScorerAgent

app = typer.Typer(
    name="ielts",
    help="IELTS Super Learner Agent - AI-powered IELTS learning assistant",
    add_completion=False,
)

console = Console()


def rich_prompt(message: str) -> str:
    """Prompt with Rich styling and proper arrow key support using prompt_toolkit."""
    # Convert Rich markup to HTML for prompt_toolkit
    # Rich: [bold yellow]You[/bold yellow] -> HTML: <style fg="ansi_yellow" bold="true">You</style>
    html_message = message

    # Simple Rich-to-HTML conversion for common styles
    replacements = [
        ("[bold yellow]", '<style fg="ansi_yellow" bold="true">'),
        ("[/bold yellow]", '</style>'),
        ("[bold cyan]", '<style fg="ansi_cyan" bold="true">'),
        ("[/bold cyan]", '</style>'),
        ("[bold green]", '<style fg="ansi_green" bold="true">'),
        ("[/bold green]", '</style>'),
        ("[yellow]", '<style fg="ansi_yellow">'),
        ("[/yellow]", '</style>'),
        ("[cyan]", '<style fg="ansi_cyan">'),
        ("[/cyan]", '</style>'),
        ("[green]", '<style fg="ansi_green">'),
        ("[/green]", '</style>'),
        ("[bold]", '<style bold="true">'),
        ("[/bold]", '</style>'),
        ("[dim]", '<style fg="ansi_black">'),
        ("[/dim]", '</style>'),
    ]

    for old, new in replacements:
        html_message = html_message.replace(old, new)

    return pt_prompt(HTML(html_message))


def get_user(user_name: str = "Student"):
    """Get or create user and initialize database."""
    init_db()
    return get_or_create_user(user_name)


@app.command()
def tutor(
    user_name: str = typer.Option("Student", "--user", "-u", help="User name"),
    classic: bool = typer.Option(False, "--classic", "-c", help="Use classic reactive mode instead of proactive"),
):
    """Interactive IELTS tutoring - a proactive tutor that guides your learning."""
    user = get_user(user_name)
    session = create_session(user.id, "tutoring")

    agent = TutorAgent(proactive=not classic)

    # Tutor starts the conversation with an opening greeting
    with console.status("[bold green]Starting tutor...[/bold green]"):
        opening_message = agent.start_conversation()

    # Display opening message
    console.print(Panel(
        opening_message,
        title="[bold cyan]IELTS Tutor[/bold cyan]",
        border_style="cyan"
    ))

    # Show hint at the start
    console.print("[dim]Type 'quit' or 'exit' to end the session.[/dim]")

    while True:
        try:
            user_input = rich_prompt("\n[bold yellow]You[/bold yellow] ")

            if user_input.lower() in ("quit", "exit", "q"):
                break

            if not user_input.strip():
                continue

            # Save user input
            save_interaction(session.id, "question", user_input)

            # Get response with conversation history
            with console.status("[bold green]Thinking...[/bold green]"):
                response = agent.ask_proactive(user_input)

            # Save response
            save_interaction(session.id, "answer", response)

            # Display response
            console.print(Panel(response, title="[bold green]Tutor[/bold green]", border_style="green"))

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type 'quit' to exit.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    end_session(session.id)
    console.print(f"[bold green]Session ended! Good luck with your IELTS preparation, {user_name}![/bold green]")


@app.command()
def practice(
    skill: str = typer.Option(..., "--skill", "-s", help="Skill: listening, reading, writing, speaking"),
    task: int = typer.Option(None, "--task", "-t", help="Task number (1-2 for writing/speaking, section for listening)"),
    topic: str = typer.Option(None, "--topic", help="Specific topic focus"),
    user_name: str = typer.Option("Student", "--user", "-u", help="User name"),
):
    """Generate practice questions for any IELTS skill."""
    skill = skill.lower()
    if skill not in SKILLS:
        console.print(f"[red]Invalid skill. Choose from: {', '.join(SKILLS)}[/red]")
        raise typer.Exit(1)

    # Inform user about text-only mode for audio skills
    if skill in ("listening", "speaking"):
        console.print(Panel(
            "[yellow]⚠️  Text-Only Mode[/yellow]\n\n"
            f"{skill.capitalize()} exercises are currently text-based only. "
            f"For {skill}, you'll read transcripts instead of audio and type responses instead of speaking. "
            "Full audio support (TTS/ASR) is planned for future updates.",
            title="Notice",
            border_style="yellow"
        ))

    user = get_user(user_name)
    session = create_session(user.id, skill, task)

    agent = PracticeAgent()

    # Build kwargs for the agent
    kwargs = {"task": task}
    if topic:
        kwargs["topic"] = topic

    try:
        with console.status(f"[bold green]Generating {skill} practice question...[/bold green]"):
            question = agent.generate_practice(skill, **kwargs)

        # Save the generated question
        save_interaction(session.id, "question", question)
        update_progress(user.id, skill)

        # Display the question
        console.print(Panel(
            question,
            title=f"[bold cyan]{skill.upper()} Practice[/bold cyan]",
            border_style="cyan",
            subtitle=f"Task: {task}" if task else None
        ))

        # Prompt for optional answer submission
        if Prompt.ask("\n[yellow]Would you like to submit an answer for scoring?[/yellow]", choices=["y", "n"], default="n") == "y":
            answer = Prompt.ask("[bold yellow]Enter your answer[/bold yellow]", multiline=True)

            if answer.strip():
                console.print("\n[bold green]Scoring your answer...[/bold green]")
                scorer = ScorerAgent()

                score_kwargs = {"task": task} if task in (1, 2) else {"part": task} if task else {}
                result = scorer.score(skill, answer, **score_kwargs)

                save_interaction(session.id, "answer", answer)
                save_interaction(session.id, "score", str(result.get("overall_band_score", result.get("band_score", 0))))

                score_display = f"""[bold cyan]Overall Band Score: {result.get('overall_band_score', result.get('band_score', 'N/A'))}[/bold cyan]

{result.get('feedback', '')}"""

                console.print(Panel(score_display, title="[bold green]Score[/bold green]", border_style="green"))

                # Update progress with score
                band_score = result.get("overall_band_score") or result.get("band_score")
                if band_score:
                    update_progress(user.id, skill, score=float(str(band_score)[:4]))

    except Exception as e:
        console.print(f"[red]Error generating practice: {e}[/red]")
        raise

    end_session(session.id)


@app.command()
def score(
    skill: str = typer.Option(..., "--skill", "-s", help="Skill: writing, speaking"),
    answer: str = typer.Option(None, "--answer", "-a", help="Answer to score (use '-' to read from stdin)"),
    answer_file: str = typer.Option(None, "--file", "-f", help="Read answer from file"),
    task: int = typer.Option(None, "--task", "-t", help="Task number (1-2 for writing, 1-3 for speaking)"),
    question: str = typer.Option(None, "--question", "-q", help="Original question/prompt"),
    user_name: str = typer.Option("Student", "--user", "-u", help="User name"),
):
    """Score an answer and get detailed feedback."""
    skill = skill.lower()
    if skill not in ("writing", "speaking"):
        console.print("[red]Scoring is currently available for writing and speaking only.[/red]")
        raise typer.Exit(1)

    # Get the answer text
    if answer_file:
        answer_text = Path(answer_file).read_text()
    elif answer == "-":
        answer_text = typer.get_text_stream("stdin").read()
    elif answer:
        answer_text = answer
    else:
        answer_text = Prompt.ask("[bold yellow]Enter your answer[/bold yellow]", multiline=True)

    if not answer_text.strip():
        console.print("[red]No answer provided.[/red]")
        raise typer.Exit(1)

    user = get_user(user_name)
    session = create_session(user.id, f"{skill}_scoring", task)

    try:
        console.print(f"[bold green]Scoring your {skill} response...[/bold green]")

        scorer = ScorerAgent()
        kwargs = {}
        if task:
            if skill == "writing":
                kwargs["task"] = task
            else:
                kwargs["part"] = task
        if question:
            kwargs["question"] = question

        result = scorer.score(skill, answer_text, **kwargs)

        # Save to database
        save_interaction(session.id, "answer", answer_text)
        save_interaction(session.id, "score", str(result.get("overall_band_score", 0)))
        save_interaction(session.id, "feedback", result.get("feedback", ""))

        band_score = result.get("overall_band_score", 0)
        update_progress(user.id, skill, score=float(band_score))

        # Display results
        console.print(Panel(
            f"[bold cyan]Overall Band Score: {band_score}[/bold cyan]",
            title=f"{skill.upper()} Score",
            border_style="cyan"
        ))

        console.print(f"\n{result.get('feedback', '')}")

        end_session(session.id)

    except Exception as e:
        console.print(f"[red]Error scoring answer: {e}[/red]")
        raise


@app.command()
def progress(
    user_name: str = typer.Option("Student", "--user", "-u", help="User name"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed session history"),
):
    """View learning progress and statistics."""
    user = get_user(user_name)

    # Get stats
    stats = get_user_stats(user.id)
    progress_data = get_progress(user.id)
    recent_sessions = get_recent_sessions(user.id, limit=10) if detailed else []

    # Header
    console.print(Panel(
        f"[bold cyan]Progress Report for: {user_name}[/bold cyan]\n\n"
        f"Total Sessions: [bold]{stats['total_sessions']}[/bold]\n"
        f"Total Interactions: [bold]{stats['total_interactions']}[/bold]\n"
        f"Overall Average Score: [bold]{stats['overall_average_score']}[/bold]",
        title="Progress Report",
        border_style="cyan"
    ))

    # Skills table
    if progress_data:
        table = Table(title="\n[bold]Skills Progress[/bold]", show_header=True, header_style="bold magenta")
        table.add_column("Skill", style="cyan", width=12)
        table.add_column("Practices", justify="center")
        table.add_column("Avg Score", justify="center")
        table.add_column("Best Score", justify="center")
        table.add_column("Last Practiced", justify="center")

        for p in progress_data:
            skill_display = p.skill.capitalize()
            avg_score = f"{p.avg_score:.1f}" if p.avg_score > 0 else "-"
            best_score = f"{p.best_score:.1f}" if p.best_score > 0 else "-"

            # Format last practiced
            if p.last_practiced:
                last_practiced = p.last_practiced.strftime("%Y-%m-%d")
            else:
                last_practiced = "-"

            table.add_row(skill_display, str(p.practice_count), avg_score, best_score, last_practiced)

        console.print(table)

    # Recent sessions (if detailed)
    if detailed and recent_sessions:
        console.print("\n[bold]Recent Sessions:[/bold]")
        for s in recent_sessions:
            status = "[green]Ended[/green]" if s["ended_at"] else "[yellow]Active[/yellow]"
            console.print(
                f"  • {s['skill'].capitalize()} "
                f"(Task {s['task']}) " if s['task'] else f"  • {s['skill'].capitalize()} "
                f"- {s['interaction_count']} interactions - {status}"
            )

    if not progress_data:
        console.print("[yellow]No practice data yet. Start with 'ielts practice'![/yellow]")


@app.command()
def reset():
    """Reset all progress (requires double confirmation)."""
    from ielts_agent.config import DB_PATH

    console.print(Panel(
        "[bold red]⚠️  DANGER: This will DELETE all your progress![/bold red]\n\n"
        "This action cannot be undone.",
        title="Reset Progress",
        border_style="red"
    ))

    # First confirmation
    confirm1 = Prompt.ask(
        "[bold yellow]Are you sure you want to reset all progress?[/bold yellow] [dim](type 'yes' to continue)[/dim]",
        default="no"
    )

    if confirm1.lower() != "yes":
        console.print("[green]Cancelled. Progress preserved.[/green]")
        return

    # Second confirmation
    confirm2 = Prompt.ask(
        "[bold red]This will permanently delete all data. Type 'DELETE' to confirm:[/bold red]",
        default=""
    )

    if confirm2 != "DELETE":
        console.print("[green]Cancelled. Progress preserved.[/green]")
        return

    # Delete database
    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
            console.print("[bold green]✓ Progress reset successfully![/bold green]")
            console.print("[dim]A fresh database will be created on your next command.[/dim]")
        else:
            console.print("[yellow]No progress data found to delete.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error deleting database: {e}[/red]")


@app.command()
def version():
    """Show version information."""
    from ielts_agent import __version__
    console.print(f"IELTS Super Learner Agent v{__version__}")


def main():
    """Main entry point."""
    # Handle case where script is run directly
    if len(sys.argv) == 1:
        console.print(Panel(
            """[bold cyan]IELTS Super Learner Agent[/bold cyan]

[bold]Available commands:[/bold]
  [green]ielts tutor[/green]         - Interactive Q&A tutoring
  [green]ielts practice[/green]      - Generate practice questions
  [green]ielts score[/green]         - Score your answers
  [green]ielts progress[/green]      - View your progress
  [red]ielts reset[/red]             - Reset all progress (destructive)

[bold]Examples:[/bold]
  [dim]python -m ielts_agent tutor[/dim]
  [dim]python -m ielts_agent practice --skill writing --task 2[/dim]
  [dim]python -m ielts_agent score --skill writing --answer "Your essay..."[/dim]
  [dim]python -m ielts_agent progress --detailed[/dim]

Run [yellow]ielts --help[/yellow] for more information.""",
            border_style="cyan"
        ))
        return

    app()


if __name__ == "__main__":
    main()
