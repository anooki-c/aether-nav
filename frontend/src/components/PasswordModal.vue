<script setup>
import { ref } from 'vue'
import { api } from '../api/client'

const props = defineProps({ open: { type: Boolean, default: false }, link: { type: Object, default: null } })
const emit = defineEmits(['update:open'])

const password = ref('')
const error = ref('')
const checking = ref(false)
const showPwd = ref(false)

function close() {
  emit('update:open', false)
  password.value = ''
  error.value = ''
  showPwd.value = false
}

async function submit() {
  if (!props.link) return
  error.value = ''
  checking.value = true
  try {
    const r = await api.unlock(props.link.id, password.value)
    if (r.ok) {
      window.open(props.link.url, '_blank')
      close()
    } else {
      error.value = r.error || '密码错误'
    }
  } catch (e) {
    error.value = e.message || '验证失败'
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <transition name="modal" appear>
    <div v-if="open && link" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <!-- Backdrop (对齐 _1 原型：模糊遮罩) -->
      <div class="absolute inset-0 bg-black/30 backdrop-blur-md" @click="close"></div>

      <!-- Modal Card -->
      <div class="modal-panel relative w-full max-w-md bg-surface rounded-2xl shadow-[0_20px_40px_-15px_rgba(108,92,231,0.15)] border border-outline-variant/30 overflow-hidden flex flex-col">
      <!-- Header with ambient glow -->
      <div class="relative pt-10 pb-6 px-8 flex flex-col items-center text-center bg-gradient-to-b from-surface-container-low to-surface">
        <div class="absolute top-8 w-24 h-24 bg-primary/10 rounded-full blur-xl mix-blend-multiply"></div>
        <!-- Lock Icon (Material Symbols, FILL) -->
        <div class="relative w-16 h-16 bg-primary-container rounded-2xl flex items-center justify-center text-on-primary-container shadow-sm mb-6 -mt-2 rotate-[-5deg]">
          <span class="material-symbols-outlined text-3xl" style="font-variation-settings: 'FILL' 1;">lock</span>
        </div>
        <h2 class="font-headline-lg text-headline-lg text-text-primary mb-2">加密链接</h2>
        <p class="font-body-md text-body-md text-text-secondary max-w-[280px]">
          此链接已加密，请输入访问密码以验证。
        </p>
      </div>

      <!-- Content -->
      <div class="px-8 pb-10">
        <form class="space-y-6" @submit.prevent="submit">
          <div class="space-y-2">
            <label class="font-label-sm text-label-sm text-on-surface-variant block ml-1" for="link-password">密码</label>
            <div class="relative group">
              <span class="absolute left-4 top-1/2 -translate-y-1/2 material-symbols-outlined text-secondary text-[20px]">key</span>
              <input
                id="link-password"
                v-model="password"
                :type="showPwd ? 'text' : 'password'"
                class="w-full bg-surface-bright border border-outline-variant rounded-xl py-3 pl-11 pr-12 text-on-surface font-body-md text-body-md focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all shadow-sm outline-none zn-input-reset"
                placeholder="请输入密码…"
                @keyup.enter="submit"
                autofocus
              />
              <button
                type="button"
                class="absolute right-4 top-1/2 -translate-y-1/2 text-secondary hover:text-primary transition-colors focus:outline-none"
                @click="showPwd = !showPwd"
              >
                <span class="material-symbols-outlined text-[20px]">{{ showPwd ? 'visibility' : 'visibility_off' }}</span>
              </button>
            </div>
            <p v-if="error" class="text-error font-body-sm text-body-sm mt-1 ml-1">{{ error }}</p>
          </div>

          <!-- Action Buttons (对齐 _1：Verify & Open + Cancel) -->
          <div class="flex flex-col gap-3 mt-8">
            <button
              type="submit"
              class="w-full bg-primary hover:bg-surface-tint text-on-primary font-headline-sm text-headline-sm rounded-xl py-3.5 flex items-center justify-center gap-2 transition-[transform,background-color,box-shadow] shadow-[0_4px_12px_rgba(108,92,231,0.25)] hover:shadow-[0_6px_16px_rgba(108,92,231,0.35)] hover:-translate-y-[1px] active:scale-[0.98] disabled:opacity-50"
              :disabled="checking"
            >
              <span>{{ checking ? '验证中…' : '验证并打开' }}</span>
              <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
            </button>
            <button
              type="button"
              class="w-full bg-transparent hover:bg-surface-container-highest text-secondary font-headline-sm text-headline-sm rounded-xl py-3 transition-colors"
              @click="close"
            >
              取消
            </button>
          </div>
        </form>
      </div>
    </div>
    </div>
  </transition>
</template>

<style scoped>
.zn-input-reset {
  border-radius: 0.75rem;
}
/* 密码弹窗材质化入场：遮罩淡入 + 面板 scale 弹入（与添加弹窗一致） */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-panel {
  transition: transform 0.42s cubic-bezier(0.32, 0.72, 0, 1), opacity 0.42s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-leave-active .modal-panel {
  transition: transform 0.22s cubic-bezier(0.32, 0.72, 0, 1), opacity 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: scale(0.96) translateY(14px);
  opacity: 0;
}
</style>
