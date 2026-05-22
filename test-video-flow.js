const axios = require('axios');

const BASE_URL = 'http://localhost:3001';
const DRAMA_ID = 1;

async function testStep(name, fn) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`测试步骤: ${name}`);
  console.log('='.repeat(60));
  try {
    const result = await fn();
    console.log(`✅ 成功:`, typeof result === 'object' ? JSON.stringify(result, null, 2) : result);
    return { success: true, data: result };
  } catch (error) {
    console.error(`❌ 失败:`, error.message);
    if (error.response) {
      console.error(`   状态码: ${error.response.status}`);
      console.error(`   响应数据:`, error.response.data);
    }
    return { success: false, error: error.message };
  }
}

async function runTests() {
  console.log('\n🚀 开始视频播放流程测试\n');

  const results = [];

  // 步骤1: 获取短剧列表
  const step1 = await testStep('1. 获取短剧列表', async () => {
    const response = await axios.get(`${BASE_URL}/api/dramas`);
    console.log(`   共获取到 ${response.data.length} 个短剧`);
    return response.data;
  });
  results.push(step1);

  // 步骤2: 获取单个短剧详情
  const drama = step1.success ? step1.data[0] : null;
  const step2 = await testStep('2. 获取短剧详情', async () => {
    if (!drama) throw new Error('无法获取短剧数据');
    const response = await axios.get(`${BASE_URL}/api/dramas/${drama.id}`);
    return response.data;
  });
  results.push(step2);

  // 步骤3: 获取剧集列表
  const step3 = await testStep('3. 获取剧集列表', async () => {
    if (!drama) throw new Error('无法获取短剧数据');
    const response = await axios.get(`${BASE_URL}/api/episodes/${drama.id}`);
    console.log(`   共获取到 ${response.data.length} 个剧集`);
    console.log(`   剧集标题示例: ${response.data[0]?.title}`);
    console.log(`   视频URL: ${response.data[0]?.video_url}`);
    return response.data;
  });
  results.push(step3);

  // 步骤4: 构建视频URL
  const episode = step3.success ? step3.data[0] : null;
  const step4 = await testStep('4. 构建视频URL', async () => {
    if (!episode) throw new Error('无法获取剧集数据');
    
    const videoUrl = episode.video_url;
    const parts = videoUrl.split('/');
    const encodedParts = parts.map(part => encodeURIComponent(part));
    const maxBuffer = 30;
    const isCurrent = true;
    
    const result = `/api/video/${encodedParts.join('/')}?maxBuffer=${maxBuffer}&current=${isCurrent}`;
    console.log(`   原始URL: ${videoUrl}`);
    console.log(`   构建URL: ${result}`);
    console.log(`   完整URL: ${BASE_URL}${result}`);
    
    return { videoUrl, constructedUrl: result, fullUrl: `${BASE_URL}${result}` };
  });
  results.push(step4);

  // 步骤5: 测试视频流请求（HEAD请求）
  const step5 = await testStep('5. 测试视频流请求 (HEAD)', async () => {
    const videoData = step4.success ? step4.data : null;
    if (!videoData) throw new Error('无法获取视频URL数据');
    
    try {
      const response = await axios.head(videoData.fullUrl);
      console.log(`   状态码: ${response.status}`);
      console.log(`   内容类型: ${response.headers['content-type']}`);
      console.log(`   内容长度: ${response.headers['content-length']}`);
      console.log(`   接受范围: ${response.headers['accept-ranges']}`);
      return response.data;
    } catch (error) {
      if (error.response) {
        console.log(`   错误状态码: ${error.response.status}`);
        console.log(`   错误响应:`, error.response.data);
        throw error;
      }
      throw error;
    }
  });
  results.push(step5);

  // 步骤6: 检查视频文件是否存在
  const step6 = await testStep('6. 检查本地视频文件是否存在', async () => {
    if (!episode) throw new Error('无法获取剧集数据');
    
    const fs = require('fs');
    const path = require('path');
    
    const externalVideoDir = 'D:\\video_data\\videos';
    const videoPath = path.join(externalVideoDir, episode.video_url);
    
    console.log(`   检查路径: ${videoPath}`);
    console.log(`   文件存在: ${fs.existsSync(videoPath)}`);
    
    if (fs.existsSync(videoPath)) {
      const stats = fs.statSync(videoPath);
      console.log(`   文件大小: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);
    }
    
    return { path: videoPath, exists: fs.existsSync(videoPath) };
  });
  results.push(step6);

  // 步骤7: 测试封面请求
  const step7 = await testStep('7. 测试封面图片请求', async () => {
    if (!drama) throw new Error('无法获取短剧数据');
    
    const coverUrl = drama.cover_url;
    const encodedCover = encodeURIComponent(coverUrl);
    const fullCoverUrl = `${BASE_URL}/covers/${encodedCover}`;
    
    console.log(`   封面文件名: ${coverUrl}`);
    console.log(`   完整URL: ${fullCoverUrl}`);
    
    try {
      const response = await axios.head(fullCoverUrl);
      console.log(`   状态码: ${response.status}`);
      console.log(`   内容类型: ${response.headers['content-type']}`);
      return response.data;
    } catch (error) {
      if (error.response) {
        console.log(`   错误状态码: ${error.response.status}`);
      }
      throw error;
    }
  });
  results.push(step7);

  // 步骤8: 测试海报保存接口
  const step8 = await testStep('8. 测试海报保存接口', async () => {
    if (!episode) throw new Error('无法获取剧集数据');
    
    const testPoster = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
    
    try {
      const response = await axios.post(`${BASE_URL}/api/episodes/${episode.id}/poster`, {
        poster: testPoster
      });
      console.log(`   状态码: ${response.status}`);
      console.log(`   响应数据:`, response.data);
      return response.data;
    } catch (error) {
      if (error.response) {
        console.log(`   错误状态码: ${error.response.status}`);
        console.log(`   错误响应:`, error.response.data);
      }
      throw error;
    }
  });
  results.push(step8);

  // 步骤9: 测试进度保存接口
  const step9 = await testStep('9. 测试进度保存接口', async () => {
    if (!drama || !episode) throw new Error('数据不完整');
    
    try {
      const response = await axios.post(`${BASE_URL}/api/history`, {
        drama_id: drama.id,
        episode_id: episode.id,
        progress: 100
      });
      console.log(`   状态码: ${response.status}`);
      console.log(`   响应数据:`, response.data);
      return response.data;
    } catch (error) {
      if (error.response) {
        console.log(`   错误状态码: ${error.response.status}`);
        console.log(`   错误响应:`, error.response.data);
      }
      throw error;
    }
  });
  results.push(step9);

  // 步骤10: 测试进度获取接口
  const step10 = await testStep('10. 测试进度获取接口', async () => {
    if (!drama) throw new Error('无法获取短剧数据');
    
    try {
      const response = await axios.get(`${BASE_URL}/api/history/${drama.id}`);
      console.log(`   状态码: ${response.status}`);
      console.log(`   响应数据:`, response.data);
      return response.data;
    } catch (error) {
      if (error.response) {
        console.log(`   错误状态码: ${error.response.status}`);
        console.log(`   错误响应:`, error.response.data);
      }
      throw error;
    }
  });
  results.push(step10);

  // 步骤11: 测试缓存状态接口
  const step11 = await testStep('11. 测试缓存状态接口', async () => {
    try {
      const response = await axios.get(`${BASE_URL}/api/cache/status`);
      console.log(`   状态码: ${response.status}`);
      console.log(`   缓存大小: ${response.data.cacheSize}`);
      console.log(`   缓存配置:`, JSON.stringify(response.data.config, null, 2));
      console.log(`   缓存条目:`, response.data.entries);
      return response.data;
    } catch (error) {
      if (error.response) {
        console.log(`   错误状态码: ${error.response.status}`);
        console.log(`   错误响应:`, error.response.data);
      }
      throw error;
    }
  });
  results.push(step11);

  // 总结
  console.log('\n\n');
  console.log('='.repeat(60));
  console.log('测试结果总结');
  console.log('='.repeat(60));
  
  const successCount = results.filter(r => r.success).length;
  const failCount = results.filter(r => !r.success).length;
  
  console.log(`\n总测试数: ${results.length}`);
  console.log(`✅ 成功: ${successCount}`);
  console.log(`❌ 失败: ${failCount}`);
  
  if (failCount > 0) {
    console.log('\n失败的测试:');
    const stepNames = [
      '1. 获取短剧列表',
      '2. 获取短剧详情', 
      '3. 获取剧集列表',
      '4. 构建视频URL',
      '5. 测试视频流请求',
      '6. 检查视频文件存在',
      '7. 测试封面请求',
      '8. 测试海报保存',
      '9. 测试进度保存',
      '10. 测试进度获取',
      '11. 测试缓存状态'
    ];
    results.forEach((result, index) => {
      if (!result.success) {
        console.log(`  - ${stepNames[index]}: ${result.error}`);
      }
    });
  }
  
  console.log('\n' + '='.repeat(60));
  
  if (failCount === 0) {
    console.log('🎉 所有测试通过！视频播放功能应该正常。');
  } else {
    console.log('⚠️  部分测试失败，请检查上方的错误信息。');
  }
}

runTests().catch(console.error);
