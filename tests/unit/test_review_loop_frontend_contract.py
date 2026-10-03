"""The review drives the loop: what needs work -> try again -> see the difference -> practise next."""

from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: WEB.joinpath(*parts).read_text(encoding="utf-8")  # noqa: E731

REVIEW = read("components", "review", "review-page.tsx")
REVIEW_VIEW = read("lib", "review-view.ts")
TRY = read("components", "review", "try-again.tsx")
ATTEMPT_VIEW = read("lib", "attempt-view.ts")
COPY = read("lib", "copy.ts")


def test_the_review_is_ordered_as_a_learning_loop() -> None:
    order = [REVIEW.index(anchor) for anchor in (
        'id="review-landed"', 'id="review-strengthen"', 'aria-labelledby="review-next"',
        'id="review-repeat"', 'id="review-answers"',
    )]
    assert order == sorted(order)


def test_one_thing_to_strengthen_and_it_can_be_acted_on() -> None:
    assert "strengthenItem(review)" in REVIEW
    assert 'answerTargets(strengthen ? 1 : 0, blocks, "couldBeClearer")' in REVIEW
    # with no matching answer the item still stands, and practice next is still offered
    assert "{strengthenFrom ? (" in REVIEW


def test_retry_targets_come_only_from_answers_the_review_marked() -> None:
    assert "block[notes].length" in REVIEW_VIEW
    assert "answerTurnId" in REVIEW_VIEW


def test_every_answer_can_be_tried_again_and_earlier_attempts_are_shown() -> None:
    assert ".attempts(sessionId)" in REVIEW
    assert "<TryAgain" in REVIEW and "<AttemptComparison" in REVIEW
    assert "latestAvailable" in REVIEW


def test_what_changed_is_read_from_aspect_pairs_not_prose() -> None:
    assert "came_through_more_clearly" in ATTEMPT_VIEW and "still_missing" in ATTEMPT_VIEW
    assert "mirrorApi.tryAgain" in TRY
    assert "Try once more" in COPY and '"Continue"' in COPY
    # The async result replaces the text field, so focus must move to a real
    # result container rather than the unmounted textarea.
    assert "resultPanel.current?.focus()" in TRY
    assert "ref={resultPanel} tabIndex={-1}" in TRY


def test_the_review_ends_with_one_practice_next_and_admits_when_there_is_none() -> None:
    assert "practiceNext(review)" in REVIEW
    assert "nextChoose" in REVIEW
    assert "practice_focus" in REVIEW_VIEW
