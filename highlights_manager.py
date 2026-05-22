#!/usr/bin/env python3
"""
高光点管理器类
提供高光点的添加、删除和查询功能
"""

import requests
import random
import json


class HighlightsManager:
    """高光点管理器"""
    
    def __init__(self, api_base='http://localhost:3001'):
        """
        初始化管理器
        
        :param api_base: API 基础地址
        """
        self.api_base = api_base
    
    def _make_request(self, method, endpoint, **kwargs):
        """
        封装 HTTP 请求
        
        :param method: HTTP 方法 (get/post/delete)
        :param endpoint: API 端点
        :param kwargs: 请求参数
        :return: 响应数据
        """
        url = f'{self.api_base}{endpoint}'
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'❌ 请求失败 [{method} {url}]: {e}')
            return None
    
    def get_dramas(self):
        """
        获取所有短剧列表
        
        :return: 短剧列表
        """
        return self._make_request('get', '/api/dramas')
    
    def get_episodes(self, drama_id):
        """
        获取指定短剧的剧集列表
        
        :param drama_id: 短剧 ID
        :return: 剧集列表
        """
        return self._make_request('get', f'/api/episodes/{drama_id}')
    
    def get_highlights(self, episode_id):
        """
        获取指定剧集的高光点
        
        :param episode_id: 剧集 ID
        :return: 高光点列表（百分比）
        """
        return self._make_request('get', f'/api/episodes/{episode_id}/highlights')
    
    def add_highlights(self, episode_id, points):
        """
        为剧集添加高光点
        
        :param episode_id: 剧集 ID
        :param points: 高光点位置列表（百分比，0-100）
        :return: 是否成功
        """
        data = {
            'episode_id': episode_id,
            'points': points
        }
        response = self._make_request(
            'post',
            '/internal/highlights',
            headers={'Content-Type': 'application/json'},
            data=json.dumps(data)
        )
        return response is not None
    
    def clear_episode_highlights(self, episode_id):
        """
        清空指定剧集的高光点
        
        :param episode_id: 剧集 ID
        :return: 删除的高光点数量
        """
        response = self._make_request('delete', f'/internal/highlights/{episode_id}')
        if response:
            return response.get('deleted', 0)
        return 0
    
    def clear_all_highlights(self):
        """
        清空所有高光点
        
        :return: 删除的高光点总数
        """
        total_deleted = 0
        dramas = self.get_dramas()
        
        if not dramas:
            return 0
        
        for drama in dramas:
            episodes = self.get_episodes(drama['id'])
            if episodes:
                for episode in episodes:
                    deleted = self.clear_episode_highlights(episode['id'])
                    total_deleted += deleted
        
        return total_deleted
    
    def list_all_highlights(self):
        """
        列出所有高光点
        
        :return: 高光点统计信息
        """
        dramas = self.get_dramas()
        
        if not dramas:
            return []
        
        all_highlights = []
        
        for drama in dramas:
            drama_info = {
                'title': drama['title'],
                'drama_id': drama['id'],
                'episodes': []
            }
            
            episodes = self.get_episodes(drama['id'])
            if episodes:
                for episode in episodes:
                    points = self.get_highlights(episode['id'])
                    if points:
                        drama_info['episodes'].append({
                            'episode_id': episode['id'],
                            'title': episode['title'],
                            'points': points
                        })
            
            if drama_info['episodes']:
                all_highlights.append(drama_info)
        
        return all_highlights
    
    def add_random_highlights(self, min_points=1, max_points=3, min_percent=50, max_percent=100):
        """
        为所有剧集随机添加高光点
        
        :param min_points: 每集最少高光点数量
        :param max_points: 每集最多高光点数量
        :param min_percent: 高光点最小百分比位置
        :param max_percent: 高光点最大百分比位置
        :return: 添加的高光点总数
        """
        dramas = self.get_dramas()
        
        if not dramas:
            print('❌ 未找到任何短剧')
            return 0
        
        total_added = 0
        
        print('🎬 开始为所有剧集添加高光点...\n')
        print(f'规则: 每集随机添加 {min_points}-{max_points} 个高光点，位置范围 {min_percent}%-{max_percent}%\n')
        
        for drama in dramas:
            drama_name = drama['title']
            print(f'处理短剧: {drama_name}')
            
            episodes = self.get_episodes(drama['id'])
            
            if not episodes:
                print('  未找到剧集')
                continue
            
            print(f'  发现 {len(episodes)} 个剧集')
            
            for episode in episodes:
                highlight_count = random.randint(min_points, max_points)
                points = []
                
                for _ in range(highlight_count):
                    percentage = min_percent + random.random() * (max_percent - min_percent)
                    points.append(round(percentage, 2))
                
                points.sort()
                
                if self.add_highlights(episode['id'], points):
                    points_str = ', '.join([f'{p:.1f}%' for p in points])
                    print(f'  剧集 {episode["id"]} ({episode["title"]}): 添加 {highlight_count} 个高光点 at {points_str}')
                    total_added += highlight_count
                else:
                    print(f'  剧集 {episode["id"]} ({episode["title"]}): 添加失败')
        
        print(f'\n✅ 完成! 共添加 {total_added} 个高光点')
        print('请刷新页面查看效果。')
        
        return total_added


def main():
    """主函数 - 添加高光点"""
    manager = HighlightsManager()
    manager.add_random_highlights()


if __name__ == '__main__':
    main()

# ====================
# 删除高光点功能（已注释）
# ====================
# def delete_demo():
#     """删除高光点示例（已注释）"""
#     manager = HighlightsManager()
#     
#     # 示例1: 列出所有高光点
#     # highlights = manager.list_all_highlights()
#     # for drama in highlights:
#     #     print(f'{drama["title"]}:')
#     #     for episode in drama['episodes']:
#     #         points_str = ', '.join([f'{p:.1f}%' for p in episode['points']])
#     #         print(f'  {episode["title"]}: {len(episode["points"])} 个高光点 [{points_str}]')
#     
#     # 示例2: 清空单个剧集的高光点
#     # deleted = manager.clear_episode_highlights(1)
#     # print(f'清空了 {deleted} 个高光点')
#     
#     # 示例3: 清空所有高光点
#     # total_deleted = manager.clear_all_highlights()
#     # print(f'总共清空了 {total_deleted} 个高光点')
# 
# if __name__ == '__main__':
#     # delete_demo()
#     pass
