<script setup>
import { ref, reactive, watch, nextTick, onBeforeUnmount } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  // 待裁剪图片的 object URL（由父组件在打开时传入）
  image: { type: String, default: '' },
})
const emit = defineEmits(['update:open', 'cancel', 'confirm'])

const imgEl = ref(null)
const busy = ref(false)
// 圆形预览遮罩，坐标与 cropperjs 的 cropBox 同步（相对于裁剪容器）
const ring = reactive({ show: false, left: 0, top: 0, size: 0 })
let cropper = null

function syncRing() {
  if (!cropper) return
  const box = cropper.getCropBoxData()
  ring.left = box.left
  ring.top = box.top
  ring.size = Math.min(box.width, box.height)
  ring.show = true
}

function destroy() {
  if (cropper) {
    cropper.destroy()
    cropper = null
  }
  ring.show = false
}

watch(
  () => [props.open, props.image],
  async ([open, image]) => {
    if (open && image) {
      await nextTick()
      destroy()
      if (window.Cropper && imgEl.value) {
        cropper = new window.Cropper(imgEl.value, {
          viewMode: 1,
          dragMode: 'move',
          aspectRatio: 1,
          autoCropArea: 1,
          cropBoxMovable: false,
          cropBoxResizable: false,
          toggleDragModeOnDblclick: false,
          background: false,
          guides: false,
          center: false,
          highlight: false,
          ready() {
            syncRing()
          },
          crop() {
            syncRing()
          },
        })
      }
    } else {
      destroy()
    }
  },
  { immediate: true }
)

onBeforeUnmount(destroy)

function close() {
  emit('update:open', false)
}
function cancel() {
  emit('cancel')
}
function zoom(delta) {
  if (cropper) cropper.zoom(delta)
}
function reset() {
  if (cropper) cropper.reset()
}

async function confirm() {
  if (!cropper) return
  busy.value = true
  try {
    // 先取方形裁剪画布（400×400）
    const src = cropper.getCroppedCanvas({ width: 400, height: 400 })
    if (!src) {
      emit('cancel')
      return
    }
    // 裁成圆形 PNG（透明背景），与各页面圆形头像显示完全一致
    const out = document.createElement('canvas')
    out.width = out.height = 400
    const ctx = out.getContext('2d')
    ctx.save()
    ctx.beginPath()
    ctx.arc(200, 200, 200, 0, Math.PI * 2)
    ctx.closePath()
    ctx.clip()
    ctx.drawImage(src, 0, 0, 400, 400)
    ctx.restore()
    out.toBlob((blob) => {
      if (blob) emit('confirm', blob)
      close()
      busy.value = false
    }, 'image/png')
  } catch (e) {
    emit('cancel')
    busy.value = false
  }
}
</script>

<template>
  <transition name="modal" appear>
    <div v-if="open" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <!-- 遮罩 -->
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="cancel"></div>

      <!-- 弹窗主体 -->
      <div class="relative w-full max-w-md bg-surface rounded-2xl shadow-[0_20px_40px_-15px_rgba(108,92,231,0.25)] border border-outline-variant/30 overflow-hidden flex flex-col">
        <div class="px-6 py-4 border-b border-outline-variant/40">
          <h3 class="font-headline-sm text-headline-sm text-text-primary">调整头像</h3>
          <p class="text-label-sm text-text-secondary mt-1">拖动图片、滚轮或下方按钮缩放，圆形区域即为头像在各页面的显示效果</p>
        </div>

        <!-- 裁剪区：固定高度，叠一个圆形预览遮罩 -->
        <div class="relative h-[340px] bg-black/5 overflow-hidden">
          <img ref="imgEl" :src="image" class="block max-w-none" alt="待裁剪" />
          <!-- 圆形预览：圈内清晰、圈外压暗，与头像实际显示一致 -->
          <div
            v-if="ring.show"
            class="pointer-events-none absolute rounded-full"
            :style="{
              left: ring.left + 'px',
              top: ring.top + 'px',
              width: ring.size + 'px',
              height: ring.size + 'px',
              boxShadow: '0 0 0 100vmax rgba(0,0,0,0.45)',
              border: '2px solid rgba(255,255,255,0.9)',
            }"
          ></div>
        </div>

        <!-- 辅助操作 -->
        <div class="flex items-center justify-center gap-2 px-6 py-3 border-t border-outline-variant/30">
          <button type="button" class="w-9 h-9 rounded-full bg-surface-container text-on-surface-variant hover:bg-surface-container-high transition-colors" title="缩小" @click="zoom(-0.1)">
            <span class="material-symbols-outlined text-[20px]">remove</span>
          </button>
          <button type="button" class="w-9 h-9 rounded-full bg-surface-container text-on-surface-variant hover:bg-surface-container-high transition-colors" title="放大" @click="zoom(0.1)">
            <span class="material-symbols-outlined text-[20px]">add</span>
          </button>
          <button type="button" class="px-3 h-9 rounded-full bg-surface-container text-on-surface-variant text-label-sm hover:bg-surface-container-high transition-colors" title="重置" @click="reset">
            重置
          </button>
        </div>

        <!-- 确认 / 取消 -->
        <div class="flex gap-3 px-6 py-4">
          <button type="button" class="flex-1 px-4 py-2.5 rounded-xl bg-surface-container text-on-surface-variant text-sm font-semibold hover:bg-surface-container-high transition-colors" @click="cancel">
            取消
          </button>
          <button type="button" :disabled="busy" class="flex-1 px-4 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-semibold shadow-sm hover:bg-primary/90 transition-all disabled:opacity-50" @click="confirm">
            {{ busy ? '处理中…' : '确定' }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
