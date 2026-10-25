<script setup>
defineProps({ name: String, size: { type: [Number, String], default: 20 } })
const paths = {
  menu: ['M4 6h16', 'M4 12h16', 'M4 18h16'],
  plus: ['M12 5v14', 'M5 12h14'],
  close: ['m6 6 12 12', 'm18 6-12 12'],
  search: ['M21 21l-5-5', 'M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z'],
  folder: ['M3 7h6l2-3h9a1 1 0 0 1 1 1v14H3Z'],
  note: ['M5 3h14v18H5Z', 'M8 8h8', 'M8 12h8', 'M8 16h5'],
  settings: ['M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z', 'm10 3-1 3-3 1-3 3v4l3 3 3 1 1 3h4l1-3 3-1 3-3v-4l-3-3-3-1-1-3Z'],
  cap: ['m3 9 9-5 9 5-9 5-9-5Z', 'M6 11v6c4 3 8 3 12 0v-6', 'M21 9v7'],
  home: ['M3 10 12 3l9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z', 'M9 21v-8h6v8'],
  history: ['M3 12a9 9 0 1 0 3-6', 'M3 3v5h5', 'M12 7v5l3 2'],
  book: ['M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Z', 'M12 5v15'],
  arrow: ['M4 12h16', 'm14 6 6 6-6 6'],
  spark: ['m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z'],
  check: ['m5 12 4 4L19 6'],
  refresh: ['M20 7a9 9 0 1 0 1 8', 'M20 3v5h-5'],
  logout: ['M9 4H4v16h5', 'M9 12h12', 'm17 8 4 4-4 4'],
  target: ['M12 3a9 9 0 1 0 9 9', 'M12 7a5 5 0 1 0 5 5', 'm12 12 9-9', 'M16 3h5v5'],
  chevron: ['m9 5 7 7-7 7'],
  send: ['m21 3-6 18-4-8-8-4 18-6Z', 'm11 13 10-10'],
  activity: ['M3 12h4l3-8 4 16 3-8h4'],
}
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path v-for="(path, index) in paths[name] || paths.spark" :key="index" :d="path" />
  </svg>
</template>
