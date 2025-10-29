<template>
  <form @submit.prevent="handleSubmit" class="task-form">
    <!-- Title (Required) -->
    <div class="form-group">
      <label for="title" class="required">タイトル</label>
      <input
        id="title"
        v-model="formData.title"
        type="text"
        placeholder="朝の服薬"
        required
        :class="{ 'error': errors.title }"
      />
      <span v-if="errors.title" class="error-message">{{ errors.title }}</span>
    </div>

    <!-- Time (Required) -->
    <div class="form-group">
      <label for="time" class="required">時刻</label>
      <input
        id="time"
        v-model="formData.time"
        type="time"
        required
        :class="{ 'error': errors.time }"
      />
      <span v-if="errors.time" class="error-message">{{ errors.time }}</span>
    </div>

    <!-- Enabled (Checkbox) -->
    <div class="form-group">
      <label class="checkbox-label">
        <input
          id="enabled"
          v-model="formData.enabled"
          type="checkbox"
        />
        <span>有効</span>
      </label>
      <p class="help-text">チェックを外すと、このタスクは実行されません</p>
    </div>

    <!-- Action Buttons -->
    <div class="form-actions">
      <button type="button" @click="handleCancel" class="btn-secondary">
        キャンセル
      </button>
      <button type="submit" class="btn-primary" :disabled="!isFormValid">
        {{ isEditMode ? '更新' : '登録' }}
      </button>
    </div>
  </form>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';

// Props
const props = defineProps({
  task: {
    type: Object,
    default: null
  }
});

// Emits
const emit = defineEmits(['submit', 'cancel']);

// Check if in edit mode
const isEditMode = computed(() => props.task !== null);

// Form data
const formData = reactive({
  title: '',
  time: '',
  enabled: true
});

// Error state
const errors = reactive({
  title: '',
  time: ''
});

// Populate form when props.task changes (edit mode)
watch(() => props.task, (newTask) => {
  if (newTask) {
    formData.title = newTask.title || '';
    formData.time = newTask.time || '';
    formData.enabled = newTask.enabled !== undefined ? newTask.enabled : true;
  } else {
    // Reset form for create mode
    resetForm();
  }
}, { immediate: true });

// Form validation check
const isFormValid = computed(() => {
  return formData.title.trim() !== '' && formData.time !== '';
});

/**
 * Validate form fields
 */
function validateForm() {
  errors.title = '';
  errors.time = '';

  if (!formData.title.trim()) {
    errors.title = 'タイトルは必須です';
  }

  if (!formData.time) {
    errors.time = '時刻は必須です';
  }

  return !errors.title && !errors.time;
}

/**
 * Handle form submission
 */
function handleSubmit() {
  if (!validateForm()) {
    return;
  }

  const taskData = {
    title: formData.title.trim(),
    time: formData.time,
    enabled: formData.enabled
  };

  emit('submit', taskData);
}

/**
 * Handle cancel action
 */
function handleCancel() {
  resetForm();
  emit('cancel');
}

/**
 * Reset form to initial state
 */
function resetForm() {
  formData.title = '';
  formData.time = '';
  formData.enabled = true;
  errors.title = '';
  errors.time = '';
}
</script>

<style scoped>
.task-form {
  max-width: 600px;
  margin: 0 auto;
}

.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
}

label.required::after {
  content: ' *';
  color: #ef4444;
}

input[type="text"],
input[type="time"] {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 1rem;
  transition: border-color 0.15s ease-in-out;
}

input[type="text"]:focus,
input[type="time"]:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

input.error {
  border-color: #ef4444;
}

.error-message {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: #ef4444;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-weight: normal;
}

.checkbox-label input[type="checkbox"] {
  width: 1.25rem;
  height: 1.25rem;
  cursor: pointer;
}

.help-text {
  margin-top: 0.5rem;
  font-size: 0.875rem;
  color: #6b7280;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
}

.btn-primary,
.btn-secondary {
  padding: 0.5rem 1.5rem;
  border: none;
  border-radius: 0.375rem;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.btn-primary {
  background-color: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #2563eb;
}

.btn-primary:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #f3f4f6;
  color: #374151;
}

.btn-secondary:hover {
  background-color: #e5e7eb;
}
</style>
