<script setup>
// 网络检测独立页面：复用 NetworkCheckModal 作为全屏内容。
// 可直接访问 /network-check 并收藏到书签栏（需管理员登录）。
import { useRouter } from 'vue-router'
import NetworkCheckModal from '../components/NetworkCheckModal.vue'

const router = useRouter()
function onClose() {
  // 关闭（点 X 或点遮罩）后返回上一页，无历史则回首页
  if (window.history.length > 1) router.back()
  else router.push('/')
}
</script>

<template>
  <NetworkCheckModal :open="true" @update:open="onClose" />
</template>
