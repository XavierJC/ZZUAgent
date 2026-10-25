<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import Icon from '../../components/Icon.vue'
import ProductDialog from '../../shared/ProductDialog.vue'
import PageHeader from '../../shared/PageHeader.vue'
import EmptyState from '../../shared/EmptyState.vue'
import LearningHome from './LearningHome.vue'
const space = useCurrentCourseSpace(), books = space.features.notebooks
const creating = ref(false), query = ref('')
const visible = computed(() => books.items.filter(b => `${b.title} ${b.description}`.toLowerCase().includes(query.value.toLowerCase())))
const date = value => new Date(value).toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })
watch(() => space.route.params.new, value => { if(value==='1')creating.value=true }, {immediate:true})
onMounted(books.load)
async function create() {
  const result = await books.create(books.creationDraft.title.trim(), books.creationDraft.description.trim())
  if (result) { creating.value = false; space.navigate('notebook', { book: result.id }) }
}
function close() { creating.value=false; if(space.route.params.new)space.replaceRoute('notebooks',{}) }
</script>
<template>
  <section class="notebooks-home">
    <PageHeader eyebrow="LEARN WITH PURPOSE · 学习空间" title="继续你的学习" description="从资料出发，在问答与练习中形成自己的理解。"><button class="product-primary" @click="creating=true"><Icon name="plus" :size="18" />新建笔记本</button></PageHeader>
    <LearningHome v-if="!books.archived" :space="space" :books="books" @create="creating=true" />
    <div v-if="books.error" class="product-message error" role="alert">{{books.error}}</div><p v-if="books.notice" class="product-message" role="status">{{books.notice}}</p><div v-if="books.pending" class="product-message" role="status">原操作正在核对，刷新不会重复创建。<button class="product-text-button" @click="books.load()">查询原回执</button><button class="product-text-button" :disabled="Boolean(books.busy)" @click="books.retry()">重试原操作（同一编号）</button></div>
    <header class="home-section-title"><h2>我的学习笔记本</h2><button class="product-text-button" @click="space.navigate('practice')">打开题库<Icon name="arrow" :size="16" /></button></header>
    <div class="notebook-list-toolbar"><div class="product-tabs"><button :class="{active:!books.archived}" @click="books.archived=false;books.load()">全部笔记本 <span>{{!books.archived?books.items.length:''}}</span></button><button :class="{active:books.archived}" @click="books.archived=true;books.load()">已归档</button></div><label class="product-search"><Icon name="search" :size="17" /><input v-model="query" aria-label="搜索笔记本" placeholder="搜索笔记本…" /></label></div>
    <div v-if="books.busy==='list' && !books.items.length" class="product-empty" role="status">正在读取你的笔记本…</div>
    <EmptyState v-else-if="!visible.length" :title="query?'没有找到对应的笔记本':books.archived?'暂无归档笔记本':'创建你的第一个学习笔记本'" :description="query?'试试其他标题关键词。':'添加资料 → 提出问题 → 查看原文 → 用练习检验理解。'"><button v-if="!query && !books.archived" class="product-primary" @click="creating=true"><Icon name="plus" :size="17" />新建笔记本</button></EmptyState>
    <div v-else class="notebook-card-grid"><button v-for="(book,index) in visible" :key="book.id" class="notebook-card" :class="`notebook-color-${index%4}`" @click="space.navigate('notebook',{book:book.id})"><div class="notebook-card-top"><span class="notebook-cover-icon"><Icon name="book" :size="25" /></span><span class="notebook-card-arrow"><Icon name="arrow" :size="19" /></span></div><h2>{{book.title}}</h2><p>{{book.description || '添加资料，记录你的理解。'}}</p><footer><span>{{book.item_count}} 项内容 · {{book.conversation_count}} 次问答</span><span>{{date(book.updated_at)}}</span></footer></button><button v-if="!books.archived" class="notebook-card notebook-create-card" @click="creating=true"><span><Icon name="plus" :size="28" /></span><strong>新的学习主题</strong><p>从空白笔记本开始</p></button></div>
    <section v-if="!books.archived && books.items.length" class="home-recent" aria-label="最近学习活动"><header class="home-section-title"><h2>最近活动</h2><span class="small muted">笔记本最近更新</span></header><ul><li v-for="book in books.items.slice(0,3)" :key="book.id"><button class="product-text-button" @click="space.navigate('notebook',{book:book.id})">{{book.title}}</button><time :datetime="book.updated_at">{{date(book.updated_at)}}</time></li></ul></section>
    <ProductDialog :open="creating" title="创建学习笔记本" @close="close"><form class="product-form" @submit.prevent="create"><p>为一个章节、一次复习或一个学习主题建立空间。</p><label for="notebook-title">笔记本名称</label><input id="notebook-title" v-model="books.creationDraft.title" required maxlength="120" placeholder="例如：模型评估与选择" /><label for="notebook-description">简短说明 <span>可选</span></label><textarea id="notebook-description" v-model="books.creationDraft.description" maxlength="1000" rows="3" placeholder="这次想要弄懂什么？" /><p v-if="books.error" role="alert" class="product-message error">{{books.error}}</p><footer><button type="button" class="product-secondary" @click="close">取消</button><button class="product-primary" :disabled="Boolean(books.busy || books.pending || !books.creationDraft.title.trim())">{{books.busy==='save'?'正在创建…':'创建并开始学习'}}</button></footer></form></ProductDialog>
  </section>
</template>
