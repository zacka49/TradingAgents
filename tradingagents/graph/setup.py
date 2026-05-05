# TradingAgents/graph/setup.py

from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents import *
from tradingagents.agents.utils.agent_states import AgentState

from .conditional_logic import ConditionalLogic


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        tool_nodes: Dict[str, ToolNode],
        conditional_logic: ConditionalLogic,
        config: Dict[str, Any] | None = None,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.conditional_logic = conditional_logic
        self.config = config or {}

    def setup_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
        """
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        # Create analyst nodes
        analyst_nodes = {}
        delete_nodes = {}
        tool_nodes = {}
        opportunity_scout_enabled = self.config.get("opportunity_scout_enabled", True)
        stock_discovery_enabled = self.config.get("stock_discovery_enabled", True)

        if opportunity_scout_enabled:
            opportunity_scout_node = create_opportunity_scout(
                self.quick_thinking_llm
            )
            opportunity_scout_delete_node = create_msg_delete()

        if stock_discovery_enabled:
            stock_discovery_node = create_stock_discovery_researcher(
                self.quick_thinking_llm
            )
            stock_discovery_delete_node = create_msg_delete()

        if "market" in selected_analysts:
            analyst_nodes["market"] = create_market_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["market"] = create_msg_delete()
            tool_nodes["market"] = self.tool_nodes["market"]

        if "social" in selected_analysts:
            analyst_nodes["social"] = create_social_media_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["social"] = create_msg_delete()
            tool_nodes["social"] = self.tool_nodes["social"]

        if "news" in selected_analysts:
            analyst_nodes["news"] = create_news_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["news"] = create_msg_delete()
            tool_nodes["news"] = self.tool_nodes["news"]

        if "fundamentals" in selected_analysts:
            analyst_nodes["fundamentals"] = create_fundamentals_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["fundamentals"] = create_msg_delete()
            tool_nodes["fundamentals"] = self.tool_nodes["fundamentals"]

        # Create researcher and manager nodes
        research_department_enabled = self.config.get("research_department_enabled", True)
        github_research_enabled = self.config.get("github_research_enabled", True)
        if research_department_enabled:
            current_news_scout_node = create_current_news_scout(
                self.quick_thinking_llm
            )
            strategy_researcher_node = create_strategy_researcher(
                self.quick_thinking_llm
            )
            copy_trading_researcher_node = create_copy_trading_researcher(
                self.quick_thinking_llm
            )
            if github_research_enabled:
                github_researcher_node = create_github_researcher(
                    self.quick_thinking_llm
                )
            research_director_node = create_research_director(
                self.deep_thinking_llm
            )
            research_department_delete_nodes = {
                "current_news": create_msg_delete(),
                "strategy": create_msg_delete(),
                "copy_trading": create_msg_delete(),
                "github_research": create_msg_delete(),
            }

        bull_researcher_node = create_bull_researcher(self.quick_thinking_llm)
        bear_researcher_node = create_bear_researcher(self.quick_thinking_llm)
        research_manager_node = create_research_manager(self.deep_thinking_llm)
        trader_node = create_trader(self.quick_thinking_llm)

        business_departments_enabled = self.config.get("business_departments_enabled", True)
        training_development_enabled = (
            business_departments_enabled
            and self.config.get("training_development_enabled", True)
        )
        if business_departments_enabled:
            chief_investment_officer_node = create_chief_investment_officer(
                self.deep_thinking_llm
            )
            trading_desk_node = create_trading_desk_strategist(
                self.quick_thinking_llm
            )
            risk_office_node = create_risk_office_guardian(
                self.quick_thinking_llm
            )
            portfolio_office_node = create_portfolio_office_allocator(
                self.quick_thinking_llm
            )
            operations_compliance_node = create_operations_compliance_auditor(
                self.quick_thinking_llm
            )
            evaluation_node = create_evaluation_analyst(
                self.quick_thinking_llm
            )
            if training_development_enabled:
                training_development_node = create_training_development_coach(
                    self.quick_thinking_llm
                )

        # Create risk analysis nodes
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        portfolio_manager_node = create_portfolio_manager(self.deep_thinking_llm)

        # Create workflow
        workflow = StateGraph(AgentState)

        if opportunity_scout_enabled:
            workflow.add_node("Opportunity Scout", opportunity_scout_node)
            workflow.add_node("Msg Clear Opportunity Scout", opportunity_scout_delete_node)
            workflow.add_node(
                "tools_opportunity_scout",
                self.tool_nodes["opportunity_scout"],
            )

        if stock_discovery_enabled:
            workflow.add_node("Stock Discovery Researcher", stock_discovery_node)
            workflow.add_node("Msg Clear Stock Discovery", stock_discovery_delete_node)
            workflow.add_node("tools_stock_discovery", self.tool_nodes["stock_discovery"])

        # Add analyst nodes to the graph
        for analyst_type, node in analyst_nodes.items():
            workflow.add_node(f"{analyst_type.capitalize()} Analyst", node)
            workflow.add_node(
                f"Msg Clear {analyst_type.capitalize()}", delete_nodes[analyst_type]
            )
            workflow.add_node(f"tools_{analyst_type}", tool_nodes[analyst_type])

        if research_department_enabled:
            workflow.add_node("Current News Scout", current_news_scout_node)
            workflow.add_node("Strategy Researcher", strategy_researcher_node)
            workflow.add_node("Copy Trading Researcher", copy_trading_researcher_node)
            if github_research_enabled:
                workflow.add_node("GitHub Researcher", github_researcher_node)
            workflow.add_node("Research Director", research_director_node)
            workflow.add_node(
                "Msg Clear Current News",
                research_department_delete_nodes["current_news"],
            )
            workflow.add_node(
                "Msg Clear Strategy",
                research_department_delete_nodes["strategy"],
            )
            workflow.add_node(
                "Msg Clear Copy Trading",
                research_department_delete_nodes["copy_trading"],
            )
            if github_research_enabled:
                workflow.add_node(
                    "Msg Clear GitHub Research",
                    research_department_delete_nodes["github_research"],
                )
            workflow.add_node("tools_current_news", self.tool_nodes["current_news"])
            workflow.add_node("tools_strategy", self.tool_nodes["strategy"])
            workflow.add_node("tools_copy_trading", self.tool_nodes["copy_trading"])
            if github_research_enabled:
                workflow.add_node("tools_github_research", self.tool_nodes["github_research"])

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        if business_departments_enabled:
            workflow.add_node("Chief Investment Officer", chief_investment_officer_node)
            workflow.add_node("Trading Desk Strategist", trading_desk_node)
            workflow.add_node("Risk Office Guardian", risk_office_node)
            workflow.add_node("Portfolio Office Allocator", portfolio_office_node)
            workflow.add_node("Operations Compliance Auditor", operations_compliance_node)
            workflow.add_node("Evaluation Analyst", evaluation_node)
            if training_development_enabled:
                workflow.add_node("Training Development Coach", training_development_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)

        # Define edges
        first_analyst = selected_analysts[0]
        first_analyst_node = f"{first_analyst.capitalize()} Analyst"

        if opportunity_scout_enabled:
            workflow.add_edge(START, "Opportunity Scout")
            workflow.add_conditional_edges(
                "Opportunity Scout",
                self.conditional_logic.should_continue_opportunity_scout,
                ["tools_opportunity_scout", "Msg Clear Opportunity Scout"],
            )
            workflow.add_edge("tools_opportunity_scout", "Opportunity Scout")
            if stock_discovery_enabled:
                workflow.add_edge("Msg Clear Opportunity Scout", "Stock Discovery Researcher")
            else:
                workflow.add_edge("Msg Clear Opportunity Scout", first_analyst_node)
        elif stock_discovery_enabled:
            workflow.add_edge(START, "Stock Discovery Researcher")
        else:
            workflow.add_edge(START, first_analyst_node)

        if stock_discovery_enabled:
            workflow.add_conditional_edges(
                "Stock Discovery Researcher",
                self.conditional_logic.should_continue_stock_discovery,
                ["tools_stock_discovery", "Msg Clear Stock Discovery"],
            )
            workflow.add_edge("tools_stock_discovery", "Stock Discovery Researcher")
            workflow.add_edge("Msg Clear Stock Discovery", first_analyst_node)

        # Connect analysts in sequence
        for i, analyst_type in enumerate(selected_analysts):
            current_analyst = f"{analyst_type.capitalize()} Analyst"
            current_tools = f"tools_{analyst_type}"
            current_clear = f"Msg Clear {analyst_type.capitalize()}"

            # Add conditional edges for current analyst
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                [current_tools, current_clear],
            )
            workflow.add_edge(current_tools, current_analyst)

            # Connect to next analyst or to Bull Researcher if this is the last analyst
            if i < len(selected_analysts) - 1:
                next_analyst = f"{selected_analysts[i+1].capitalize()} Analyst"
                workflow.add_edge(current_clear, next_analyst)
            elif research_department_enabled:
                workflow.add_edge(current_clear, "Current News Scout")
            else:
                workflow.add_edge(current_clear, "Bull Researcher")

        # Add remaining edges
        if research_department_enabled:
            workflow.add_conditional_edges(
                "Current News Scout",
                self.conditional_logic.should_continue_current_news,
                ["tools_current_news", "Msg Clear Current News"],
            )
            workflow.add_edge("tools_current_news", "Current News Scout")
            workflow.add_edge("Msg Clear Current News", "Strategy Researcher")

            workflow.add_conditional_edges(
                "Strategy Researcher",
                self.conditional_logic.should_continue_strategy,
                ["tools_strategy", "Msg Clear Strategy"],
            )
            workflow.add_edge("tools_strategy", "Strategy Researcher")
            workflow.add_edge("Msg Clear Strategy", "Copy Trading Researcher")

            workflow.add_conditional_edges(
                "Copy Trading Researcher",
                self.conditional_logic.should_continue_copy_trading,
                ["tools_copy_trading", "Msg Clear Copy Trading"],
            )
            workflow.add_edge("tools_copy_trading", "Copy Trading Researcher")
            if github_research_enabled:
                workflow.add_edge("Msg Clear Copy Trading", "GitHub Researcher")
                workflow.add_conditional_edges(
                    "GitHub Researcher",
                    self.conditional_logic.should_continue_github_research,
                    ["tools_github_research", "Msg Clear GitHub Research"],
                )
                workflow.add_edge("tools_github_research", "GitHub Researcher")
                workflow.add_edge("Msg Clear GitHub Research", "Research Director")
            else:
                workflow.add_edge("Msg Clear Copy Trading", "Research Director")
            workflow.add_edge("Research Director", "Bull Researcher")

        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )
        if business_departments_enabled:
            workflow.add_edge("Research Manager", "Chief Investment Officer")
            workflow.add_edge("Chief Investment Officer", "Trader")
            workflow.add_edge("Trader", "Trading Desk Strategist")
            workflow.add_edge("Trading Desk Strategist", "Risk Office Guardian")
            workflow.add_edge("Risk Office Guardian", "Aggressive Analyst")
        else:
            workflow.add_edge("Research Manager", "Trader")
            workflow.add_edge("Trader", "Aggressive Analyst")
        workflow.add_conditional_edges(
            "Aggressive Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Conservative Analyst": "Conservative Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Conservative Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Neutral Analyst": "Neutral Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Aggressive Analyst": "Aggressive Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )

        if business_departments_enabled:
            workflow.add_edge("Portfolio Manager", "Portfolio Office Allocator")
            workflow.add_edge("Portfolio Office Allocator", "Operations Compliance Auditor")
            workflow.add_edge("Operations Compliance Auditor", "Evaluation Analyst")
            if training_development_enabled:
                workflow.add_edge("Evaluation Analyst", "Training Development Coach")
                workflow.add_edge("Training Development Coach", END)
            else:
                workflow.add_edge("Evaluation Analyst", END)
        else:
            workflow.add_edge("Portfolio Manager", END)

        return workflow
