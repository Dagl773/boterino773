# src/on1builder/cli/dashboard_cmd.py
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.align import Align

from on1builder.config.loaders import settings
from on1builder.utils.logging_config import get_logger
from on1builder.utils.notification_service import NotificationService

logger = get_logger(__name__)
console = Console()
app = typer.Typer(help="Real-time dashboard for ON1Builder MEV bot.")

class DashboardManager:
    """Manages the real-time dashboard display."""
    
    def __init__(self):
        self._notification_service = NotificationService()
        self._is_running = False
        self._update_interval = 2.0  # Update every 2 seconds
        
    async def start_dashboard(self, refresh_rate: float = 2.0):
        """Start the real-time dashboard."""
        self._update_interval = refresh_rate
        self._is_running = True
        
        console.print(Panel.fit(
            "[bold blue]ON1Builder MEV Bot Dashboard[/bold blue]\n"
            "[dim]Real-time monitoring and analytics[/dim]",
            border_style="blue"
        ))
        
        try:
            with Live(self._create_dashboard_layout(), refresh_per_second=4, screen=True) as live:
                while self._is_running:
                    try:
                        # Update dashboard data
                        updated_layout = await self._update_dashboard_data()
                        live.update(updated_layout)
                        
                        await asyncio.sleep(self._update_interval)
                        
                    except KeyboardInterrupt:
                        console.print("\n[yellow]Dashboard stopped by user[/yellow]")
                        break
                    except Exception as e:
                        logger.error(f"Dashboard error: {e}")
                        await asyncio.sleep(5)
                        
        except Exception as e:
            console.print(f"[red]Dashboard failed to start: {e}[/red]")
    
    def _create_dashboard_layout(self) -> Layout:
        """Create the initial dashboard layout."""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="left_panel"),
            Layout(name="right_panel")
        )
        
        layout["left_panel"].split_column(
            Layout(name="performance"),
            Layout(name="opportunities")
        )
        
        layout["right_panel"].split_column(
            Layout(name="chains"),
            Layout(name="alerts")
        )
        
        # Initialize with placeholder content
        layout["header"].update(self._create_header())
        layout["performance"].update(self._create_performance_panel())
        layout["opportunities"].update(self._create_opportunities_panel())
        layout["chains"].update(self._create_chains_panel())
        layout["alerts"].update(self._create_alerts_panel())
        layout["footer"].update(self._create_footer())
        
        return layout
    
    async def _update_dashboard_data(self) -> Layout:
        """Update dashboard with real-time data."""
        layout = self._create_dashboard_layout()
        
        # Update each panel with current data
        layout["performance"].update(await self._get_performance_data())
        layout["opportunities"].update(await self._get_opportunities_data())
        layout["chains"].update(await self._get_chains_data())
        layout["alerts"].update(await self._get_alerts_data())
        
        return layout
    
    def _create_header(self) -> Panel:
        """Create the dashboard header."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        header_text = Text()
        header_text.append("ON1Builder MEV Bot", style="bold blue")
        header_text.append(" | ")
        header_text.append(f"Status: ", style="dim")
        header_text.append("RUNNING", style="bold green")
        header_text.append(" | ")
        header_text.append(f"Time: {current_time}", style="dim")
        
        return Panel(Align.center(header_text), border_style="blue")
    
    async def _get_performance_data(self) -> Panel:
        """Get real-time performance data."""
        try:
            # This would integrate with your actual performance tracking
            performance_data = {
                "total_profit_eth": 0.125,
                "total_trades": 47,
                "success_rate": 89.4,
                "avg_profit_per_trade": 0.0027,
                "total_gas_spent_eth": 0.023,
                "net_profit_eth": 0.102,
                "roi_percentage": 443.5
            }
            
            table = Table(title="Performance Metrics", show_header=True, header_style="bold magenta")
            table.add_column("Metric", style="cyan", no_wrap=True)
            table.add_column("Value", style="green", justify="right")
            table.add_column("Change", style="yellow", justify="right")
            
            table.add_row("Total Profit", f"{performance_data['total_profit_eth']:.6f} ETH", "+0.008")
            table.add_row("Net Profit", f"{performance_data['net_profit_eth']:.6f} ETH", "+0.006")
            table.add_row("Total Trades", str(performance_data['total_trades']), "+3")
            table.add_row("Success Rate", f"{performance_data['success_rate']:.1f}%", "+2.1%")
            table.add_row("Avg Profit/Trade", f"{performance_data['avg_profit_per_trade']:.6f} ETH", "+0.0001")
            table.add_row("ROI", f"{performance_data['roi_percentage']:.1f}%", "+15.2%")
            
            return Panel(table, title="📊 Performance", border_style="green")
            
        except Exception as e:
            return Panel(f"Error loading performance data: {e}", title="📊 Performance", border_style="red")
    
    async def _get_opportunities_data(self) -> Panel:
        """Get real-time opportunities data."""
        return self._create_opportunities_panel()
    
    async def _get_chains_data(self) -> Panel:
        """Get multi-chain status data."""
        try:
            # This would integrate with your chain workers
            chains_data = {
                "ethereum": {"status": "active", "balance": 0.45, "opportunities": 5},
                "polygon": {"status": "active", "balance": 125.3, "opportunities": 4},
                "arbitrum": {"status": "active", "balance": 0.23, "opportunities": 3}
            }
            
            table = Table(title="Multi-Chain Status", show_header=True, header_style="bold magenta")
            table.add_column("Chain", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Balance", style="yellow", justify="right")
            table.add_column("Opps", style="blue", justify="right")
            
            for chain, data in chains_data.items():
                status_style = "green" if data['status'] == 'active' else "red"
                table.add_row(
                    chain.title(),
                    f"[{status_style}]{data['status'].upper()}[/{status_style}]",
                    f"{data['balance']:.2f}",
                    str(data['opportunities'])
                )
            
            return Panel(table, title="⛓️ Chains", border_style="blue")
            
        except Exception as e:
            return Panel(f"Error loading chains data: {e}", title="⛓️ Chains", border_style="red")
    
    async def _get_alerts_data(self) -> Panel:
        """Get recent alerts and notifications."""
        try:
            # This would integrate with your notification service
            alerts = [
                {"level": "info", "message": "Arbitrage opportunity detected", "time": "2m ago"},
                {"level": "warning", "message": "High gas prices detected", "time": "5m ago"},
                {"level": "success", "message": "Flashloan executed successfully", "time": "8m ago"},
                {"level": "info", "message": "New token pair added", "time": "12m ago"}
            ]
            
            alert_text = Text()
            for alert in alerts[:5]:  # Show last 5 alerts
                if alert['level'] == 'info':
                    alert_text.append("ℹ️ ", style="blue")
                elif alert['level'] == 'warning':
                    alert_text.append("⚠️ ", style="yellow")
                elif alert['level'] == 'success':
                    alert_text.append("✅ ", style="green")
                elif alert['level'] == 'error':
                    alert_text.append("❌ ", style="red")
                
                alert_text.append(f"{alert['message']} ", style="white")
                alert_text.append(f"({alert['time']})", style="dim")
                alert_text.append("\n")
            
            return Panel(alert_text, title="🔔 Recent Alerts", border_style="yellow")
            
        except Exception as e:
            return Panel(f"Error loading alerts: {e}", title="🔔 Recent Alerts", border_style="red")
    
    def _create_footer(self) -> Panel:
        """Create the dashboard footer."""
        footer_text = Text()
        footer_text.append("Press ", style="dim")
        footer_text.append("Ctrl+C", style="bold red")
        footer_text.append(" to exit | ", style="dim")
        footer_text.append("Refresh: ", style="dim")
        footer_text.append(f"{self._update_interval}s", style="bold green")
        
        return Panel(Align.center(footer_text), border_style="blue")

    def _create_opportunities_panel(self) -> Panel:
        """Create live arbitrage opportunities panel."""
        try:
            # Get top 5 opportunities (mock data for now)
            opportunities = self._get_top_opportunities()
            
            if not opportunities:
                content = "[yellow]No profitable opportunities detected[/yellow]"
            else:
                # Create opportunities table
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Token Pair", style="cyan")
                table.add_column("ROI %", style="green")
                table.add_column("Est. Profit", style="yellow")
                table.add_column("Inclusion Score", style="blue")
                
                for opp in opportunities:
                    # Color code based on ROI
                    roi_style = self._get_roi_color(opp['roi'])
                    
                    table.add_row(
                        opp['token_pair'],
                        f"[{roi_style}]{opp['roi']:.2f}%[/{roi_style}]",
                        f"{opp['estimated_profit']:.6f} ETH",
                        f"{opp['inclusion_score']:.1f}%"
                    )
                
                content = table
            
            return Panel(
                content,
                title="[bold cyan]Live Arbitrage Opportunities[/bold cyan]",
                border_style="cyan"
            )
            
        except Exception as e:
            logger.error(f"Error creating opportunities panel: {e}")
            return Panel(
                "[red]Error loading opportunities[/red]",
                title="[bold cyan]Live Arbitrage Opportunities[/bold cyan]",
                border_style="red"
            )
    
    def _get_top_opportunities(self) -> List[Dict]:
        """Get top 5 arbitrage opportunities."""
        try:
            # Mock data - in production this would come from opportunity detector
            return [
                {
                    'token_pair': 'ETH/USDC',
                    'roi': 12.5,
                    'estimated_profit': 0.045,
                    'inclusion_score': 85.2
                },
                {
                    'token_pair': 'WBTC/ETH',
                    'roi': 8.7,
                    'estimated_profit': 0.032,
                    'inclusion_score': 72.1
                },
                {
                    'token_pair': 'USDC/DAI',
                    'roi': 6.2,
                    'estimated_profit': 0.018,
                    'inclusion_score': 65.8
                },
                {
                    'token_pair': 'LINK/ETH',
                    'roi': 4.8,
                    'estimated_profit': 0.012,
                    'inclusion_score': 58.3
                },
                {
                    'token_pair': 'UNI/USDC',
                    'roi': 3.1,
                    'estimated_profit': 0.008,
                    'inclusion_score': 45.7
                }
            ]
        except Exception as e:
            logger.error(f"Error getting opportunities: {e}")
            return []
    
    def _get_roi_color(self, roi: float) -> str:
        """Get color for ROI display."""
        if roi > 10:
            return "bold green"
        elif roi > 5:
            return "yellow"
        else:
            return "red"

@app.command(name="start")
def start_dashboard(
    refresh_rate: float = typer.Option(2.0, "--refresh", "-r", help="Dashboard refresh rate in seconds")
):
    """Start the real-time dashboard."""
    try:
        dashboard = DashboardManager()
        asyncio.run(dashboard.start_dashboard(refresh_rate))
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to start dashboard: {e}[/red]")
        raise typer.Exit(1)

@app.command(name="status")
def show_status():
    """Show current bot status."""
    try:
        # This would integrate with your actual bot status
        status_data = {
            "bot_status": "running",
            "uptime": "2h 15m 30s",
            "active_chains": 3,
            "total_profit": "0.125 ETH",
            "success_rate": "89.4%"
        }
        
        table = Table(title="ON1Builder Status", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        for metric, value in status_data.items():
            table.add_row(metric.replace("_", " ").title(), str(value))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error getting status: {e}[/red]")
        raise typer.Exit(1)

@app.command(name="analytics")
def show_analytics():
    """Show detailed analytics."""
    try:
        # This would integrate with your analytics engine
        analytics_data = {
            "strategy_performance": {
                "arbitrage": {"success_rate": 92.1, "avg_profit": 0.008},
                "front_run": {"success_rate": 78.5, "avg_profit": 0.012},
                "back_run": {"success_rate": 85.2, "avg_profit": 0.009},
                "sandwich": {"success_rate": 65.8, "avg_profit": 0.025}
            },
            "market_conditions": {
                "volatility": "medium",
                "gas_prices": "high",
                "competition": "low"
            }
        }
        
        # Strategy performance table
        strategy_table = Table(title="Strategy Performance", show_header=True, header_style="bold magenta")
        strategy_table.add_column("Strategy", style="cyan")
        strategy_table.add_column("Success Rate", style="green", justify="right")
        strategy_table.add_column("Avg Profit", style="yellow", justify="right")
        
        for strategy, data in analytics_data["strategy_performance"].items():
            strategy_table.add_row(
                strategy.replace("_", " ").title(),
                f"{data['success_rate']:.1f}%",
                f"{data['avg_profit']:.6f} ETH"
            )
        
        console.print(strategy_table)
        console.print()
        
        # Market conditions
        market_table = Table(title="Market Conditions", show_header=True, header_style="bold magenta")
        market_table.add_column("Factor", style="cyan")
        market_table.add_column("Status", style="green")
        
        for factor, status in analytics_data["market_conditions"].items():
            market_table.add_row(factor.replace("_", " ").title(), status.title())
        
        console.print(market_table)
        
    except Exception as e:
        console.print(f"[red]Error getting analytics: {e}[/red]")
        raise typer.Exit(1)

@app.command(name="config")
def show_config():
    """Show current configuration."""
    try:
        config_data = {
            "Chains": ", ".join(map(str, settings.chains)),
            "Min Profit": f"{settings.min_profit_eth} ETH",
            "Max Gas Price": f"{settings.max_gas_price_gwei} Gwei",
            "Flashloan Enabled": str(settings.flashloan_enabled),
            "ML Enabled": str(settings.ml_enabled),
            "Front Running": str(settings.front_running_enabled),
            "Back Running": str(settings.back_running_enabled),
            "Sandwich Attacks": str(settings.sandwich_attacks_enabled)
        }
        
        table = Table(title="Current Configuration", show_header=True, header_style="bold magenta")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        for setting, value in config_data.items():
            table.add_row(setting, value)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error getting configuration: {e}[/red]")
        raise typer.Exit(1) 