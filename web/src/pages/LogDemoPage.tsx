/**
 * LogDemoPage.tsx — 日志系统演示页面
 *
 * 演示日志面板的各种使用场景：
 * - 基础日志显示
 * - API调用日志
 * - 工作流执行日志
 * - 错误处理日志
 * - 过滤和清空功能
 */
import React, { useState } from 'react';
import { logger } from '../lib/logger';

export function LogDemoPage() {
  const [demoInProgress, setDemoInProgress] = useState(false);

  // 场景1：基础日志显示
  const demonstrateBasicLogging = () => {
    logger.info('🎬 开始演示基础日志功能');

    logger.debug('这是调试信息 - 用于开发调试');
    logger.info('这是信息日志 - 一般操作记录');
    logger.warn('这是警告信息 - 需要注意的问题');
    logger.error('这是错误信息 - 操作失败');

    logger.info('✅ 基础日志演示完成');
  };

  // 场景2：API调用日志
  const demonstrateApiLogging = async () => {
    logger.info('🎬 开始演示API调用日志');

    // 模拟API调用
    logger.apiRequest('POST', '/api/data-sources', { scenario: 'finance_v1' });

    await new Promise(resolve => setTimeout(resolve, 500));

    logger.apiResponse('POST', '/api/data-sources', 200, 512);
    logger.info('✅ 数据源上传成功');

    logger.apiRequest('GET', '/api/rulesets/123');
    await new Promise(resolve => setTimeout(resolve, 300));
    logger.apiResponse('GET', '/api/rulesets/123', 200, 128);
    logger.info('✅ 规则集获取成功');

    // 模拟API错误
    logger.apiRequest('DELETE', '/api/rulesets/999');
    await new Promise(resolve => setTimeout(resolve, 200));
    logger.apiError('DELETE', '/api/rulesets/999', new Error('规则集不存在'));
    logger.warn('⚠️ 规则集删除失败');

    logger.info('✅ API调用日志演示完成');
  };

  // 场景3：工作流日志
  const demonstrateWorkflowLogging = async () => {
    logger.info('🎬 开始演示工作流日志');

    // 模拟工作流执行
    logger.workflow('upload', 'running', '上传数据源文件...');
    await new Promise(resolve => setTimeout(resolve, 800));
    logger.workflow('upload', 'done', '数据源上传完成');

    logger.workflow('learn', 'running', '开始规则学习...');
    await new Promise(resolve => setTimeout(resolve, 1000));
    logger.info('合并人工规则 5 条');
    logger.info('NetNomos 发现规则 12 条');
    logger.workflow('learn', 'done', '规则学习完成');

    logger.workflow('explain', 'running', '生成规则解释...');
    await new Promise(resolve => setTimeout(resolve, 600));
    logger.workflow('explain', 'done', '规则解释生成完成');

    logger.workflow('validate', 'running', '验证新数据...');
    await new Promise(resolve => setTimeout(resolve, 900));
    logger.warn('发现 3 条违规记录');
    logger.workflow('validate', 'done', '数据验证完成');

    logger.info('✅ 工作流日志演示完成');
  };

  // 场景4：错误处理日志
  const demonstrateErrorLogging = async () => {
    logger.info('🎬 开始演示错误处理日志');

    // 模拟各种错误场景
    logger.error('❌ 文件上传失败：文件大小超过限制');
    logger.error('❌ API连接失败：后端服务无响应');
    logger.warn('⚠️ SSE连接超时，降级为轮询模式');
    logger.warn('⚠️ Ollama服务不可用，使用mock模式');

    // 模拟错误恢复
    await new Promise(resolve => setTimeout(resolve, 500));
    logger.info('🔄 自动重试中...');
    await new Promise(resolve => setTimeout(resolve, 800));
    logger.info('✅ 连接已恢复');

    logger.info('✅ 错误处理日志演示完成');
  };

  // 场景5：SSE事件日志
  const demonstrateSSELogging = async () => {
    logger.info('🎬 开始演示SSE事件日志');

    logger.sseConnection('connecting');
    await new Promise(resolve => setTimeout(resolve, 300));
    logger.sseConnection('connected');

    // 模拟SSE事件流
    for (let i = 0; i < 5; i++) {
      await new Promise(resolve => setTimeout(resolve, 400));
      logger.sseEvent('workflow', {
        id: `evt-${i}`,
        stage: ['upload', 'learn', 'validate'][i % 3],
        status: 'running',
        description: `步骤 ${i + 1} 执行中...`
      });
    }

    logger.sseConnection('disconnected');
    logger.info('✅ SSE事件日志演示完成');
  };

  // 综合演示：执行所有场景
  const runFullDemo = async () => {
    setDemoInProgress(true);
    logger.info('🎪 开始完整演示...');
    logger.info('═'.repeat(50));

    await demonstrateBasicLogging();
    await new Promise(resolve => setTimeout(resolve, 1000));

    await demonstrateApiLogging();
    await new Promise(resolve => setTimeout(resolve, 1000));

    await demonstrateWorkflowLogging();
    await new Promise(resolve => setTimeout(resolve, 1000));

    await demonstrateErrorLogging();
    await new Promise(resolve => setTimeout(resolve, 1000));

    await demonstrateSSELogging();
    await new Promise(resolve => setTimeout(resolve, 1000));

    logger.info('═'.repeat(50));
    logger.info('🎉 完整演示结束！');
    logger.info('💡 提示：点击日志面板上的过滤按钮查看不同级别的日志');
    setDemoInProgress(false);
  };

  return (
    <div className="page-pad">
      <div className="max-w-4xl mx-auto">
        <div className="glass-card">
          <h1 className="text-3xl font-bold mb-4">📋 日志系统演示</h1>
          <p className="text-gray-600 mb-8">
            点击下面的按钮演示日志面板的各种功能。请确保已打开日志面板（点击右下角的"显示日志"按钮）。
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 基础演示按钮 */}
            <button
              onClick={demonstrateBasicLogging}
              disabled={demoInProgress}
              className="demo-btn bg-blue-500 hover:bg-blue-600 text-white px-6 py-4 rounded-lg font-semibold transition disabled:opacity-50"
            >
              <div className="text-2xl mb-2">🎯</div>
              <div>场景1：基础日志</div>
              <div className="text-sm font-normal opacity-80">显示不同级别的日志</div>
            </button>

            <button
              onClick={demonstrateApiLogging}
              disabled={demoInProgress}
              className="demo-btn bg-green-500 hover:bg-green-600 text-white px-6 py-4 rounded-lg font-semibold transition disabled:opacity-50"
            >
              <div className="text-2xl mb-2">📡</div>
              <div>场景2：API调用</div>
              <div className="text-sm font-normal opacity-80">追踪API请求和响应</div>
            </button>

            <button
              onClick={demonstrateWorkflowLogging}
              disabled={demoInProgress}
              className="demo-btn bg-purple-500 hover:bg-purple-600 text-white px-6 py-4 rounded-lg font-semibold transition disabled:opacity-50"
            >
              <div className="text-2xl mb-2">⚙️</div>
              <div>场景3：工作流</div>
              <div className="text-sm font-normal opacity-80">追踪完整工作流执行</div>
            </button>

            <button
              onClick={demonstrateErrorLogging}
              disabled={demoInProgress}
              className="demo-btn bg-red-500 hover:bg-red-600 text-white px-6 py-4 rounded-lg font-semibold transition disabled:opacity-50"
            >
              <div className="text-2xl mb-2">⚠️</div>
              <div>场景4：错误处理</div>
              <div className="text-sm font-normal opacity-80">显示错误和警告信息</div>
            </button>

            <button
              onClick={demonstrateSSELogging}
              disabled={demoInProgress}
              className="demo-btn bg-yellow-500 hover:bg-yellow-600 text-white px-6 py-4 rounded-lg font-semibold transition disabled:opacity-50"
            >
              <div className="text-2xl mb-2">📨</div>
              <div>场景5：SSE事件</div>
              <div className="text-sm font-normal opacity-80">实时事件流日志</div>
            </button>

            <button
              onClick={runFullDemo}
              disabled={demoInProgress}
              className="demo-btn bg-gradient-to-r from-pink-500 to-orange-500 hover:from-pink-600 hover:to-orange-600 text-white px-6 py-4 rounded-lg font-semibold transition disabled:opacity-50"
            >
              <div className="text-2xl mb-2">🎪</div>
              <div>完整演示</div>
              <div className="text-sm font-normal opacity-80">执行所有场景</div>
            </button>
          </div>

          {demoInProgress && (
            <div className="mt-8 text-center">
              <div className="inline-flex items-center gap-2 bg-blue-100 text-blue-800 px-4 py-2 rounded-full">
                <div className="animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
                演示进行中，请观察日志面板...
              </div>
            </div>
          )}

          <div className="mt-8 p-4 bg-gray-100 rounded-lg">
            <h3 className="font-semibold mb-2">💡 使用提示：</h3>
            <ul className="text-sm text-gray-700 space-y-1">
              <li>1. 点击右下角的"📋 显示日志"按钮打开日志面板</li>
              <li>2. 点击上面的场景按钮执行演示</li>
              <li>3. 观察日志面板中的实时更新</li>
              <li>4. 尝试使用日志面板的过滤功能</li>
              <li>5. 点击"清空日志"按钮重新开始</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
