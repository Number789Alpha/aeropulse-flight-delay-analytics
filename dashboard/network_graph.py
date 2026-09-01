"""
AeroPulse: Airline & Flight Delay Analytics — Network Analysis Layer
Uses NetworkX to build a directed graph of airport hubs weighted by average delay
and flight volume, computing Betweenness Centrality and PageRank to spot bottlenecks.
"""

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

def build_delay_network(df_routes):
    """
    Constructs a directed graph from flight route records and calculates hub centrality.
    df_routes expected cols: orig_code, dest_code, total_flights, avg_arr_delay
    """
    G = nx.DiGraph()

    for _, r in df_routes.iterrows():
        u = str(r["orig_code"])
        v = str(r["dest_code"])
        vol = float(r.get("total_flights", 1))
        delay = max(0.1, float(r.get("avg_arr_delay", 0.1)))

        G.add_edge(u, v, weight=delay, volume=vol)

    # Compute graph metrics
    betweenness = nx.betweenness_centrality(G, weight="weight")
    in_degree = dict(G.in_degree())
    out_degree = dict(G.out_degree())
    try:
        pagerank = nx.pagerank(G, weight="volume")
    except Exception:
        pagerank = {n: 1.0 / len(G) for n in G.nodes()}

    nodes_data = []
    for n in G.nodes():
        nodes_data.append({
            "hub": n,
            "betweenness_centrality": round(betweenness.get(n, 0.0), 4),
            "pagerank_score": round(pagerank.get(n, 0.0), 4),
            "inbound_connections": in_degree.get(n, 0),
            "outbound_connections": out_degree.get(n, 0),
            "total_corridors": in_degree.get(n, 0) + out_degree.get(n, 0)
        })

    df_hubs = pd.DataFrame(nodes_data).sort_values("betweenness_centrality", ascending=False)
    return G, df_hubs

def generate_network_layout_figure(G, df_hubs, title="Hub Propagation Centrality Network"):
    """
    Generates a 2D spring-layout Network graph with Plotly.
    """
    pos = nx.spring_layout(G, seed=42, k=0.35)

    # Edge traces
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.7, color='rgba(0, 229, 255, 0.25)'),
        hoverinfo='none',
        mode='lines'
    )

    # Node traces
    node_x = []
    node_y = []
    node_text = []
    node_size = []
    node_color = []

    betweenness_map = dict(zip(df_hubs["hub"], df_hubs["betweenness_centrality"]))

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        bw = betweenness_map.get(node, 0.0)
        deg = G.degree(node)
        node_size.append(min(38, max(14, int(bw * 400 + 12))))
        node_color.append(bw)
        node_text.append(f"<b>{node}</b><br>Betweenness Centrality: {bw:.4f}<br>Connections: {deg}")

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[n for n in G.nodes()],
        textposition="top center",
        textfont=dict(size=10, color="#FFFFFF"),
        hovertext=node_text,
        marker=dict(
            showscale=True,
            colorscale='YlOrRd',
            reversescale=False,
            color=node_color,
            size=node_size,
            colorbar=dict(
                thickness=12,
                title=dict(text='Betweenness', font=dict(color='#FFF', size=11)),
                tickfont=dict(color='#FFF', size=9)
            ),
            line=dict(width=1.5, color='rgba(255,255,255,0.7)')
        )
    )

    fig = go.Figure(data=[edge_trace, node_trace],
        layout=go.Layout(
            title=dict(text=title, font=dict(color='#FFF', size=14)),
            showlegend=False,
            hovermode='closest',
            margin=dict(b=10, l=10, r=10, t=35),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(15,23,42,0.6)'
        )
    )
    return fig
