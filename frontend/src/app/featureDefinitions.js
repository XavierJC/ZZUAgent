import { computed } from 'vue'
import { useNotesWorkspace } from '../features/notes/useNotesWorkspace.js'
import { useStudyWorkbench } from '../features/chat/useStudyWorkbench.js'
import { useCourseDocuments } from '../features/materials/useCourseDocuments.js'
import { useTeachingLinks } from '../features/materials/useTeachingLinks.js'
import { useResourceLibrary } from '../features/materials/useResourceLibrary.js'
import { usePersonalBank } from '../features/practice/usePersonalBank.js'
import { useSelfAssessments } from '../features/learning/useSelfAssessments.js'
import { useStudyGuidance } from '../features/learning/useStudyGuidance.js'
import { useReviewPractice } from '../features/learning/useReviewPractice.js'
import { useCourseBuilder } from '../features/authoring/useCourseBuilder.js'
import { useKnowledgeArchitecture } from '../features/authoring/useKnowledgeArchitecture.js'

const pendingDraft = s => Boolean(s.dirty || s.pending)
export const featureDefinitions = {
  notes: {
    create: c => useNotesWorkspace(c.client, c.student, c.notesStore),
    needsSave: pendingDraft, hasUnsaved: pendingDraft,
  },
  chat: {
    create: c => useStudyWorkbench(c.client, c.student, undefined, {
      session: () => c.flow.session, scope: () => c.flow.data?.release?.retrieval_scope || null,
      contexts: () => c.flow.data?.explanations || [], revision: () => c.w.snapshot?.revision,
      refresh: () => c.flow.load(),
    }),
    hasUnsaved: s => Boolean(s.busy === 'ask' || s.pendingId),
  },
  documents: {
    create: c => useCourseDocuments(c.client, c.student),
    needsSave: s => Boolean(s.file || s.pending),
    hasUnsaved: s => Boolean(s.file || s.pending),
  },
  practice: {
    create: c => usePersonalBank(c.client, c.student),
    needsSave: pendingDraft, hasUnsaved: pendingDraft,
  },
  library: {
    create: c => useResourceLibrary(c.client, c.student),
    needsSave: pendingDraft, hasUnsaved: pendingDraft,
  },
  assessment: {
    create: c => useSelfAssessments(c.client, c.student),
    needsSave: pendingDraft, hasUnsaved: pendingDraft,
  },
  guides: {
    create: c => {
      const self = c.use('assessment')
      return useStudyGuidance(c.client, c.student, computed(() => self.overview),
        computed(() => c.peek('chat')?.chosen || []), computed(() => self.canGenerate))
    },
    hasUnsaved: s => Boolean(s.busy === 'generate' || s.pendingId),
  },
  review: { create: c => useReviewPractice(c.client, c.w) },
  builder: {
    create: c => useCourseBuilder(c.client, c.student),
    needsSave: s => Boolean(s.editor || s.pending), hasUnsaved: pendingDraft,
  },
  architecture: {
    create: c => useKnowledgeArchitecture(c.client, c.student),
    needsSave: pendingDraft, hasUnsaved: pendingDraft,
  },
  links: {
    create: c => useTeachingLinks(c.client, c.student),
    needsSave: s => Boolean(s.pending || s.draft?.document_id),
    hasUnsaved: s => Boolean(s.pending || s.draft?.document_id && s.draft?.excerpt_md),
  },
}

// Reading and guide generation use different capabilities. Entering progress
// does not create a chat or fetch private note bodies and chat history.
export const pageFeatures = {
  study: ['chat', 'documents', 'assessment'],
  practice: ['practice', 'documents'],
  insights: ['assessment', 'guides'],
  notes: ['notes'],
  learn: ['assessment', 'review'],
  history: [],
  resources: ['library'],
  materials: ['library', 'documents', 'links'],
  bank: ['practice'],
  architecture: ['architecture'],
  builder: ['builder'],
  publish: ['builder'],
}
