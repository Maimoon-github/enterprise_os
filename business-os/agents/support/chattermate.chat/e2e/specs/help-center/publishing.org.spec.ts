import { test, expect, createArticle, enableHelpCenter, setArticleStatus, unique } from '@e2e'

// Turning the help center on is an org-wide setting, so this runs in the serial
// `org` project. The public site is unauthenticated: exactly what is published,
// nothing else.

test('only published articles are on the public help center @help-center', async ({ adminApi, anonymousPage }) => {
  const site = await enableHelpCenter(adminApi)
  const code = unique('HC')
  const article = await createArticle(adminApi, {
    question: `How do I reset my router ${code}?`,
    answer: `Hold the reset button for ten seconds. Reference ${code}.`,
  })
  const articleUrl = `${site}/a/${article.slug}`

  // A draft is invisible to the public: not listed, and its URL is not found.
  await anonymousPage.goto(site)
  await expect(anonymousPage.getByText(code)).toHaveCount(0)
  expect((await anonymousPage.request.get(articleUrl)).status()).toBe(404)

  await setArticleStatus(adminApi, article.id, 'published')
  await anonymousPage.goto(articleUrl)
  await expect(anonymousPage.getByRole('heading', { name: `How do I reset my router ${code}?` })).toBeVisible()
  await expect(anonymousPage.getByText('Hold the reset button for ten seconds.')).toBeVisible()
  await anonymousPage.goto(site)
  await expect(anonymousPage.getByText(`How do I reset my router ${code}?`)).toBeVisible()

  // Unpublishing takes it down again.
  await setArticleStatus(adminApi, article.id, 'draft')
  expect((await anonymousPage.request.get(articleUrl)).status()).toBe(404)
})
