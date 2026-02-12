/**
 * 分类信息动态加载模块
 * 从后端API获取分类统计数据，动态更新首页显示
 * 简化版本：移除冗余配置，让浏览器遵循后端缓存指令
 */

// 分类信息动态加载
async function loadCategoryInfo() {
    const categoryElement = document.getElementById('category-info');
    if (!categoryElement) return;

    try {
        console.log('正在获取分类信息...');
        
        // 使用默认请求配置，让浏览器遵循后端的缓存指令
        const response = await fetch('/api/categories');

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('分类API响应:', data);

        // 解析分类数据
        const totalCategories = data.total_categories || 0;
        const categoriesObj = data.categories || {};
        const categoryNames = Object.keys(categoriesObj);
        
        // 生成显示文本
        let displayText;
        if (categoryNames.length > 0) {
            // 取前4个分类名称
            const displayCategories = categoryNames.slice(0, 4);
            const categoriesText = displayCategories.join('、');
            displayText = `${totalCategories}+ 图片分类，覆盖${categoriesText}等多种场景`;
        } else {
            // 没有分类时的默认显示
            displayText = '10+ 图片分类，覆盖自然、城市、动物、艺术等多种场景';
        }

        // 更新页面显示
        categoryElement.textContent = displayText;
        console.log('分类信息更新成功:', displayText);

    } catch (error) {
        console.error('获取分类信息失败:', error);
        // 出错时显示默认文本
        categoryElement.textContent = '10+ 图片分类，覆盖自然、城市、动物、艺术等多种场景';
    }
}

// 页面加载完成后自动执行
document.addEventListener('DOMContentLoaded', function() {
    console.log('监听页面加载完成事件');
    // 延迟执行确保DOM完全加载
    setTimeout(loadCategoryInfo, 100);
});

// 导出函数供外部调用（如果需要）
window.loadCategoryInfo = loadCategoryInfo;