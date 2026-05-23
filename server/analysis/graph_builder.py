"""
人物关系图谱构建模块 - NetworkX
"""
import json
import networkx as nx
from pathlib import Path
from typing import Dict, List, Optional


class GraphBuilder:
    """人物关系图谱构建 - NetworkX"""

    def __init__(self, graph_file: str):
        self.graph_file = Path(graph_file)
        self.graph_file.parent.mkdir(parents=True, exist_ok=True)

    def build_episode_graph(
        self,
        analysis_result: Dict,
        episode_id: int
    ) -> nx.Graph:
        """
        构建单集人物关系图

        Args:
            analysis_result: 分析结果字典
            episode_id: 剧集ID

        Returns:
            NetworkX图对象
        """
        G = nx.Graph()
        G.graph["episode_id"] = episode_id

        for char in analysis_result.get("characters", []):
            G.add_node(
                char["id"],
                name=char["name"],
                role=char.get("role", "supporting"),
                description=char.get("description", ""),
                first_appearance=char.get("first_appearance", 0)
            )

        for rel in analysis_result.get("relationships", []):
            G.add_edge(
                rel["source_id"],
                rel["target_id"],
                relation=rel.get("type", "unknown"),
                strength=rel.get("strength", 0.5),
                description=rel.get("description", ""),
                episodes=[episode_id]
            )

        return G

    def merge_global_graph(
        self,
        episode_graph: nx.Graph,
        drama_id: int
    ) -> nx.Graph:
        """
        将剧集图谱合并到全局图谱

        Args:
            episode_graph: 单集图谱
            drama_id: 剧ID

        Returns:
            更新后的全局图谱
        """
        global_graph = self.load_global_graph(drama_id)

        for node, attrs in episode_graph.nodes(data=True):
            if node in global_graph.nodes:
                for key, value in attrs.items():
                    if key not in global_graph.nodes[node]:
                        global_graph.nodes[node][key] = value

                if "episodes" not in global_graph.nodes[node]:
                    global_graph.nodes[node]["episodes"] = []

                ep_id = episode_graph.graph["episode_id"]
                if ep_id not in global_graph.nodes[node]["episodes"]:
                    global_graph.nodes[node]["episodes"].append(ep_id)
            else:
                global_graph.add_node(
                    node,
                    **attrs,
                    episodes=[episode_graph.graph["episode_id"]]
                )

        for u, v, attrs in episode_graph.edges(data=True):
            if global_graph.has_edge(u, v):
                existing_episodes = global_graph.edges[u, v].get("episodes", [])
                ep_id = episode_graph.graph["episode_id"]

                if ep_id not in existing_episodes:
                    existing_episodes.append(ep_id)
                    global_graph.edges[u, v]["episodes"] = existing_episodes

                if attrs.get("strength", 0) > global_graph.edges[u, v].get("strength", 0):
                    global_graph.edges[u, v]["strength"] = attrs["strength"]
            else:
                global_graph.add_edge(u, v, **attrs)

        return global_graph

    def load_global_graph(self, drama_id: int) -> nx.Graph:
        """加载全局图谱"""
        if not self.graph_file.exists():
            G = nx.Graph()
            G.graph["drama_id"] = drama_id
            return G

        with open(self.graph_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return nx.node_link_graph(data)

    def save_global_graph(self, graph: nx.Graph):
        """保存全局图谱"""
        data = nx.node_link_data(graph)

        with open(self.graph_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"图谱已保存到: {self.graph_file}")
        print(f"  - 节点数: {graph.number_of_nodes()}")
        print(f"  - 边数: {graph.number_of_edges()}")

    def get_character_network(
        self,
        character_id: str,
        depth: int = 2
    ) -> Dict:
        """
        获取指定人物的社交网络

        Args:
            character_id: 人物ID
            depth: 关系深度

        Returns:
            网络数据字典
        """
        graph = self.load_global_graph(1)

        if character_id not in graph:
            return {"error": f"人物 {character_id} 不存在"}

        neighbors = nx.single_source_shortest_path_length(
            graph, character_id, cutoff=depth
        )
        subgraph = graph.subgraph(neighbors.keys())

        return nx.node_link_data(subgraph)

    def get_character_info(
        self,
        character_id: str
    ) -> Optional[Dict]:
        """获取人物详细信息"""
        graph = self.load_global_graph(1)

        if character_id not in graph:
            return None

        node_data = dict(graph.nodes[character_id])

        neighbors = list(graph.neighbors(character_id))
        relationships = []

        for neighbor in neighbors:
            edge_data = graph.edges[character_id, neighbor]
            relationships.append({
                "character_id": neighbor,
                "character_name": graph.nodes[neighbor].get("name", neighbor),
                "relation": edge_data.get("relation", "unknown"),
                "strength": edge_data.get("strength", 0.5),
                "description": edge_data.get("description", ""),
                "episodes": edge_data.get("episodes", [])
            })

        node_data["relationships"] = relationships
        node_data["connection_count"] = len(neighbors)

        return node_data

    def export_to_d3_json(self, drama_id: int) -> Dict:
        """
        导出为D3.js可用的JSON格式

        Args:
            drama_id: 剧ID

        Returns:
            D3.js格式的图数据
        """
        graph = self.load_global_graph(drama_id)

        nodes = []
        for node_id, attrs in graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "name": attrs.get("name", node_id),
                "role": attrs.get("role", "supporting"),
                "description": attrs.get("description", ""),
                "episodes": attrs.get("episodes", []),
                "group": 1 if attrs.get("role") == "protagonist" else 2
            })

        links = []
        for u, v, attrs in graph.edges(data=True):
            links.append({
                "source": u,
                "target": v,
                "relation": attrs.get("relation", "unknown"),
                "strength": attrs.get("strength", 0.5)
            })

        return {
            "nodes": nodes,
            "links": links
        }
