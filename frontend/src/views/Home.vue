<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { store } from '../store'
import { api } from '../api/client'
import SearchHero from '../components/SearchHero.vue'
import LinkCard from '../components/LinkCard.vue'
import SquareCard from '../components/SquareCard.vue'
import EntityIcon from '../components/EntityIcon.vue'
import PasswordModal from '../components/PasswordModal.vue'
import draggable from 'vuedraggable'

const groups = ref([])
const loading = ref(false)
const pendingLink = ref(null)
const showPwd = ref(false)
// 首页区块入场仅首次挂载播放一次：切换内外网/搜索会经 loading 态卸载重建区块，
// 若持续重放错峰入场会显得迟缓（Emil：高频操作应去除或大幅缩减动画）。
const entranceDone = ref(false)

// 仅登录用户、站点开启拖拽排序、且允许主页编辑时，才允许主页卡片拖拽
const canDrag = computed(() => !!store.token && store.dragSortEnabled && store.allowHomeEdit)

// 首页卡片布局（系统设置 → 显示设置）：列数 / 紧凑 / 密度
// 列数动态类需以字面量存在，供 Tailwind JIT 扫描生成
const COL_CLASS = {
  2: 'lg:grid-cols-2',
  3: 'lg:grid-cols-3',
  4: 'lg:grid-cols-4',
  5: 'lg:grid-cols-5',
  6: 'lg:grid-cols-6',
  7: 'lg:grid-cols-7',
  8: 'lg:grid-cols-8',
}
const gridClass = computed(() => {
  const cols = COL_CLASS[store.columns] || 'lg:grid-cols-4'
  const gap = store.compactMode ? 'gap-3' : 'gap-6'
  return `grid grid-cols-2 md:grid-cols-3 ${cols} ${gap}`
})
// 紧凑或紧凑密度时卡片更紧凑
const cardCompact = computed(() => store.compactMode || store.density === 'compact')

// 搜索框是否固定在顶部（后台"系统设置 → 搜索框位置"）
const searchFixed = computed(() => store.searchBoxPos === 'fixed')

// 主内容区分类顺序必须与侧边栏一致：
// 按分类树做深度优先展开（父分类 → 其子分类），得到顺序索引后对 groups 排序。
// 树中不存在的分类（异常数据）排到最后，保持后端原有相对顺序。
const orderedGroups = computed(() => {
  const order = new Map()
  let i = 0
  const walk = (nodes) => {
    for (const n of nodes || []) {
      order.set(n.id, i++)
      walk(n.children)
    }
  }
  walk(store.tree)
  // 分类「主页显示」关闭或已归档时整组不渲染（后端也会过滤，这里做一层前端兜底）
  return groups.value
    .filter((g) => g.category && g.category.visible !== false && !g.category.archived)
    .map((g, idx) => ({ g, idx }))
    .sort((a, b) => {
      const ai = order.has(a.g.category.id) ? order.get(a.g.category.id) : Number.MAX_SAFE_INTEGER
      const bi = order.has(b.g.category.id) ? order.get(b.g.category.id) : Number.MAX_SAFE_INTEGER
      if (ai !== bi) return ai - bi
      return a.idx - b.idx
    })
    .map((x) => x.g)
})

async function load(query) {
  loading.value = true
  try {
    const data = await api.links(store.network, query || '')
    groups.value = data.groups || []
  } catch (e) {
    groups.value = []
  } finally {
    loading.value = false
    // 首次数据就绪后，下一帧标记入场完成，后续加载不再重放动画
    if (!entranceDone.value) await nextTick().then(() => (entranceDone.value = true))
  }
}

function onSearch({ q }) {
  load(q)
}

function openLink(link) {
  if (link.has_password) {
    pendingLink.value = link
    showPwd.value = true
    return
  }
  if (link.url) {
    // 访问埋点：异步上报，不阻塞跳转
    if (link.id) api.trackClick(link.id).catch(() => {})
    window.open(link.url, '_blank')
  }
}

// 拖拽结束：按当前用户保存该分类下的卡片顺序（PRD item 6）
async function onDragEnd(group) {
  const ids = group.links.map((l) => l.id)
  try {
    await api.reorderLinks(group.category.id, ids)
  } catch (e) {
    // 保存失败时保留本地顺序，不强制刷新
  }
}

onMounted(() => load())
// 内外网模式切换 / 链接变更后刷新
watch(() => store.network, () => load())
watch(() => store.linksVersion, () => load())
// 站点设置（拖拽开关）变化后刷新以应用/取消拖拽
watch(() => store.dragSortEnabled, () => load())
// 侧边栏选中分类变化后刷新（重新拉取，保证排序/可见性最新）
// 点击侧边栏分类：主页始终显示全部卡片，仅平滑滚动到对应分类区域
watch(() => store.scrollNonce, async () => {
  if (!store.scrollTargetId) return
  await nextTick()
  // 优先滚动到点击分类自身的区域；若该分类下无链接（无区域），退回父分类区域
  const el =
    document.getElementById('cat-section-' + store.activeCategoryId) ||
    document.getElementById('cat-section-' + store.scrollTargetId)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
})
</script>

<template>
  <div class="w-full px-4 lg:px-24 pb-24">
    <!-- 搜索框：fixed=在滚动容器内吸顶（带毛玻璃背景，向两侧扩展铺满）；吸顶位置在顶栏之下，不与顶栏头像菜单重叠 -->
    <div
      :class="searchFixed ? 'sticky top-0 z-20 lg:-mx-24 lg:px-24 bg-background/85 backdrop-blur-md border-b border-outline-variant/30' : ''"
    >
      <SearchHero :sticky="searchFixed" @search="onSearch" />
    </div>

    <!-- 吸顶模式下搜索条下方补一段留白，避免首个分类紧贴 -->
    <div :class="searchFixed ? 'pt-6' : 'pt-6'">
    <Transition name="fade">
      <div v-if="loading" key="loading" class="text-center text-on-surface-variant py-12 font-body-md text-body-md">加载中…</div>

      <div v-else-if="!groups.length" key="empty" class="text-center py-20">
        <span class="material-symbols-outlined text-5xl text-outline-variant empty-pop">search_off</span>
      <p class="mt-3 font-headline-sm text-headline-sm text-on-surface-variant">暂无可见链接</p>
      <p class="font-body-sm text-body-sm text-on-surface-variant mt-1">试试切换内外网<span v-if="store.allowHomeEdit">，或使用顶栏的 + 添加链接</span></p>
    </div>

      <div v-else key="content">
      <section
        v-for="(g, gi) in orderedGroups"
      :key="g.category.id"
      :id="'cat-section-' + g.category.id"
      :class="['mb-10', !entranceDone ? 'home-group' : '', searchFixed ? 'scroll-mt-[168px]' : 'scroll-mt-20']"
      :style="!entranceDone ? { animationDelay: gi * 35 + 'ms' } : null"
    >
      <h3 class="font-headline-md text-headline-md text-on-background mb-6 flex items-center gap-2">
        <EntityIcon :icon="g.category.icon" fallback="folder_open" :size="20" :alt="g.category.name" class="text-brand" />
        {{ g.category.name }}
      </h3>

      <!-- 桌面端：横向卡片（可拖拽） -->
      <div class="hidden md:block">
        <draggable
          v-if="canDrag"
          :list="g.links"
          item-key="id"
          :group="{ name: 'cat-' + g.category.id }"
          :animation="200"
          :class="gridClass"
          @end="onDragEnd(g)"
        >
          <template #item="{ element }">
            <LinkCard :link="element" :draggable="true" :compact="cardCompact" @open="openLink" />
          </template>
        </draggable>

        <!-- 静态网格（访客 / 未开启拖拽） -->
        <TransitionGroup v-else :class="gridClass" name="card" tag="div">
          <LinkCard v-for="l in g.links" :key="l.id" :link="l" :compact="cardCompact" @open="openLink" />
        </TransitionGroup>
      </div>

      <!-- 移动端：4 列 1:1 方形卡（仅 icon + 标题） -->
      <div class="md:hidden grid grid-cols-4 gap-3">
        <SquareCard v-for="l in g.links" :key="l.id" :link="l" @open="openLink" />
      </div>
    </section>
      </div>
    </Transition>
    </div>

    <PasswordModal v-model:open="showPwd" :link="pendingLink" />
  </div>
</template>

<style scoped>
/* 首页分类区块入场：轻微上浮 + 淡入（弹簧曲线），按索引错峰，营造"内容抵达"的层次感。
   全局 prefers-reduced-motion 会将其降级为瞬时出现。 */
@keyframes homeGroupIn {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}
.home-group {
  animation: homeGroupIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
}
/* 加载态 ↔ 内容/空状态：淡入淡出（out-in，避免同屏重叠） */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 160ms cubic-bezier(0.23, 1, 0.32, 1);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
/* 空状态图标：轻微弹入（rare/first-time 的 delight 预算） */
.empty-pop {
  animation: emptyPop 300ms cubic-bezier(0.32, 0.72, 0, 1) both;
}
@keyframes emptyPop {
  from { opacity: 0; transform: scale(0.94); }
  to { opacity: 1; transform: scale(1); }
}
/* 链接卡片新增进入 + 重排平滑（仅静态网格；拖拽网格由 vuedraggable 处理） */
.card-enter-active {
  transition: opacity 220ms cubic-bezier(0.23, 1, 0.32, 1), transform 220ms cubic-bezier(0.23, 1, 0.32, 1);
}
.card-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.card-move {
  transition: transform 250ms cubic-bezier(0.23, 1, 0.32, 1);
}
</style>
