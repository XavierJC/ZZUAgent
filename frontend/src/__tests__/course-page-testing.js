import { vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

// Route pages are real dynamic imports. Wait for their mount and subsequent
// read-only restore, rather than assuming every page is in the entry bundle.
export async function settleCoursePage() {
  await flushPromises()
  await vi.dynamicImportSettled()
  await flushPromises()
}
