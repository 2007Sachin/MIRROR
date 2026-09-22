/**
 * Central copy for Mirror. Tone rules and glossary: docs/copy-guide.md.
 * Everything here is shown to people, so it is linted for banned words
 * (scripts/copy_lint.py). Keep identifiers and API field names out of it.
 */

export const meta = {
  title: "Mirror by Pathwisse",
  description:
    "A calm space to practice talking about your experience, with a friendly voice conversation and a kind, clear reflection afterward.",
  skipLink: "Skip to content",
  byline: "by Pathwisse",
} as const;

export const landing = {
  hero: {
    eyebrow: "A calm space to practice",
    title: "Find the words for your experience.",
    subline:
      "Mirror reads your resume and your target role, then has a relaxed voice conversation with you. Afterward, you get a gentle reflection on what came through clearly and what to practice next.",
    primaryCta: "Start practicing",
    secondaryCta: "See a sample reflection",
    underButtons: "Your resume · Your target role · A friendly conversation · A kind reflection",
  },
  heroCard: {
    ariaLabel: "A sample reflection",
    label: "A sample reflection",
    storyLabel: "Your story",
    story: "“Improved checkout conversion by 18%.”",
    followUpLabel: "A follow-up you might hear",
    followUp: "What part of the experiment did you lead yourself?",
    cameThroughLabel: "What came through",
    cameThrough: [
      ["Your role", "Clearly"],
      ["The numbers behind it", "Mostly"],
      ["Scope", "Clearly"],
      ["Results", "Clearly"],
    ],
    readinessLabel: "Readiness",
    roleReadiness: "Role readiness",
    interviewReadiness: "Interview readiness",
    roleRange: "72–80%",
    interviewRange: "64–73%",
  },
  problem: {
    eyebrow: "Why practice",
    title: "Your resume opens the door. Your words carry you through.",
    body: "Every interview starts with a resume. But in the room, people remember how you explain what you did: what was yours, how you knew it worked, and what you learned. That's a skill, and it gets easier with practice.",
    cards: [
      {
        title: "Skills speak through stories",
        body: "Hiring is moving from job titles toward what people can actually do.",
        source: "LinkedIn Economic Graph, 2025",
        href: "https://economicgraph.linkedin.com/content/dam/me/economicgraph/en-us/PDF/skills-based-hiring-march-2025.pdf",
      },
      {
        title: "Structure helps",
        body: "Interviews built around the role tend to be more reliable than open-ended chats.",
        source: "McDaniel et al., 1994",
        href: "https://home.ubalt.edu/tmitch/645/articles/McDanieletal1994CriterionValidityInterviewsMeta.pdf",
      },
      {
        title: "Polish is a start",
        body: "A well-written resume can't yet show what was yours, how big the work was, or how you knew it worked. Talking it through can.",
        source: "Mirror product framing",
        href: null,
      },
    ],
  },
  how: {
    eyebrow: "How Mirror works",
    title: "One gentle step at a time.",
    steps: [
      { n: "01", title: "Your resume", body: "Your experience becomes our starting point." },
      { n: "02", title: "Your target role", body: "The role sets the context." },
      { n: "03", title: "A friendly conversation", body: "Follow-up questions help you find the details." },
      { n: "04", title: "What came through", body: "What's clear and what's still forming both stay visible." },
      { n: "05", title: "Your reflection", body: "Everything turns into a small next step." },
    ],
  },
  moment: {
    eyebrow: "Details, one question at a time",
    title: "Your story, a little more clearly each time.",
    body: "Mirror isn't here to decide whether you're truthful. It asks for a little more context so your story comes across the way you mean it.",
    story: "“Improved checkout conversion by 18%.”",
    questions: [
      "What was yours to lead?",
      "How did you arrive at 18%?",
      "What were you comparing against?",
      "Who else helped?",
    ],
  },
  looksAt: {
    eyebrow: "What Mirror looks at",
    title: "Not how confident you sound. How clearly your story comes through.",
    items: [
      "What you led yourself",
      "The size and edges of the work",
      "Results and how you measured them",
      "Whether your story stays consistent",
      "How it connects to the role",
      "How clearly you explain when asked more",
      "How much this conversation can speak to",
    ],
  },
  sample: {
    eyebrow: "A sample reflection",
    roleReadiness: "Role readiness",
    roleRange: "72–80%",
    roleNote: "Several parts of your experience line up well with this role.",
    interviewReadiness: "Interview readiness",
    interviewRange: "64–73%",
    interviewNote: "Your starting point and role could be a little clearer.",
    cameThroughLabel: "What came through",
    cameThrough: "1 clearly · 1 mostly · 1 not explored yet",
    nextLabel: "Next step",
    next: "Practice describing where you started, what you led, and how big the work was.",
  },
  comparison: {
    eyebrow: "Not another generic mock interview",
    title: "More than a generic mock interview.",
    ariaLabel: "Mirror compared with a generic mock interview",
    head: ["Approach", "Mirror", "A generic mock interview"],
    rows: [
      ["Approach", "Built around your resume and role", "The same questions for everyone"],
      ["Your resume", "Becomes the starting point", "Often left in the background"],
      [
        "Follow-ups",
        "Gently explore your role, scope, and measures",
        "May move on after the first answer",
      ],
      ["Feedback", "A kind, clear reflection with next steps", "General tips or a number"],
      ["When it's unsure", "Says “not enough to say yet”", "Often guesses"],
    ],
  },
  trust: {
    eyebrow: "Trust and limits",
    title: "Kind, and honest about its limits.",
    points: [
      "No live ratings during your conversation.",
      "Every point in your reflection links back to a moment from your session.",
      "“Not enough to say yet” is a perfectly good outcome.",
      "Mirror is a practice partner, not a hiring decision-maker.",
      "Your resume and conversations stay private, and are not intentionally used to train third-party models.",
    ],
  },
  final: {
    eyebrow: "Start where you are",
    title: "Walk into your next interview knowing your own story.",
    cta: "Start practicing",
  },
  footer:
    "Mirror reflects on what came up in this session. AI can make mistakes, and we're still learning how well these reflections match real interview outcomes.",
} as const;

export const report = {
  title: (role: string) => `Your reflection · ${role}`,
  backToSpace: "Your space",
  navLabel: "Reflection navigation",
  loadingLabel: "Loading your reflection",
  summary: { eyebrow: "Your summary", levelToday: "Your level today" },
  shorterNote:
    "From a shorter conversation, so a few areas say “not enough to say yet.”",
  readiness: {
    eyebrow: "Readiness",
    title: "Two signals, kept separate.",
    role: "Role readiness",
    interview: "Interview readiness",
    none: "Not enough to say yet",
    caption:
      "These appear as ranges because one conversation can only show so much.",
  },
  signal: {
    STRONG: "A clear picture",
    MODERATE: "A partial picture",
    WEAK: "A small picture",
    NONE: "Not enough to say yet",
  } as Record<string, string>,
  cameThrough: {
    eyebrow: "What came through",
    title: "What you shared, and how it came through",
    intro: "This is a gentle look at your own words. It starts with what came through clearly.",
    source: "Where it came from",
    note: "A short note",
    empty: "There wasn't anything to show here for this conversation.",
    noQuotes: "No matching moments were captured for this one.",
    sourceDocument: "Your resume or documents",
    interviewTurn: "Your conversation",
    groups: {
      held: "Came through clearly",
      partially_held: "Mostly came through",
      walked_back: "Refined during the conversation",
      contradicted: "Worth revisiting",
      insufficient_evidence: "Not enough to say yet",
      unverified: "Not yet explored",
    },
  },
  skills: {
    eyebrow: "Your skills",
    title: "How each skill came through",
    clear: "Came through clearly",
    mostly: "Mostly came through",
    none: "Not enough to say yet",
    empty: "Notes on each skill will appear here when they're ready.",
  },
  moments: {
    eyebrow: "Moments from your session",
    title: "Moments worth remembering",
    empty: "No time-linked moments were recorded.",
    labels: {
      STRONG_EVIDENCE: "Came through strongly",
      RECOVERY: "Found your footing",
      OWNERSHIP_CLARIFICATION: "Your role became clearer",
      UNSUPPORTED_SCALE: "A number worth explaining",
      TECHNICAL_DEPTH: "Technical depth",
    } as Record<string, string>,
  },
  growth: {
    eyebrow: "Your main growth area",
    intro:
      "Mirror picked one area from this conversation as a starting point, so your next practice session has a clear direction.",
    exerciseLabel: "A tiny exercise to try",
    areas: {
      OWNERSHIP_SPECIFICITY: {
        name: "Describing what you led",
        exercise: "Pick one project and say, in two sentences, what you did yourself and what your team did.",
      },
      TECHNICAL_DEPTH: {
        name: "Going a little deeper on how it works",
        exercise: "Choose one topic and explain it out loud, as if to a friend. Include one choice you made and why.",
      },
      ANSWER_STRUCTURE: {
        name: "Shaping your answers",
        exercise: "Try answering in three short parts: the situation, what you did, and what happened.",
      },
      OUTCOME_EVIDENCE: {
        name: "Explaining your results",
        exercise: "Take one number from your resume. Say where it started, what changed, and how you knew.",
      },
      COMPOSURE_UNDER_PROBE: {
        name: "Staying comfortable when asked more",
        exercise: "Before you answer a follow-up, take two slow breaths. A pause is always welcome.",
      },
      ROLE_SKILL_GAP: {
        name: "Building skills for this role",
        exercise: "Choose one skill from the job description, and write down one small way to practice it this week.",
      },
    } as Record<string, { name: string; exercise: string }>,
    fallback: {
      name: "One area to explore",
      exercise: "Pick one moment from your session and tell it again, a little more slowly.",
    },
  },
  plan: {
    eyebrow: "A small plan for this week",
    title: "Three small steps",
    steps: [
      "Try the tiny exercise above once, out loud.",
      "Pick one moment from your session and tell it again in your own words.",
      "Come back for another practice session whenever you feel ready.",
    ],
  },
  trust: {
    title: "What this reflection means, and what it doesn't",
    points: [
      "This reflects this one conversation.",
      "AI can make mistakes. If something doesn't sound right, you're welcome to tell us.",
      "Anything that didn't come up is never guessed.",
      "This is a practice reflection, not a hiring decision.",
    ],
    outcomeNotValidated: "We're still learning how well these reflections match real interview outcomes.",
    outcomeOther: "Outcome check:",
  },
  closing: {
    eyebrow: "A closing note",
    body: "Talking about your own work takes real effort, and you gave this your time. Thank you for that. Whenever you're ready, another conversation will be here.",
  },
  completed: "Completed",
  states: {
    processingTitle: "Reflecting on your answers",
    processingBody: "Mirror is looking at what you shared and how it connects to the role. Thank you for your patience.",
    returnToSpace: "Return to your space",
    failedTitle: "We couldn't finish your reflection just now",
    unavailableTitle: "Your reflection isn't available right now",
    savedRetry:
      "Your interview has been saved. Mirror couldn't finish reflecting on your answers, so it can be tried again without repeating the conversation.",
    longWait: "Your reflection is taking a little longer than expected. Please check back shortly.",
    notFound: "We couldn't find that reflection.",
    loadFailed: "We couldn't load your reflection just now. Please check your connection and try again.",
    retryFailed: "We couldn't try that again just now. Please try again in a moment.",
    retry: "Try again",
    retrying: "Trying again…",
  },
} as const;

export const voiceRoom = {
  doneAnswering: "I'm done answering",
  stepAway: {
    button: "Step away",
    title: "Need to step away?",
    body: "Your conversation is saved up to here. You can pick it back up whenever you like.",
    save: "Save and continue later",
    saving: "Saving your place…",
    end: "End and get my reflection",
    stay: "Stay in the conversation",
    saveFailed: "We couldn't save your place just now. Please try again.",
  },
  endConfirm: {
    body: "End here and get your reflection? It will be based on what we've talked about so far, so it may say \u201cnot enough to say yet\u201d in a few places.",
    confirm: "End and get my reflection",
    cancel: "Not yet",
  },
  draft: {
    title: "Your conversation is saved",
    copy: "Pick up where you left off.",
    continue: "Continue conversation",
    end: "End and get my reflection",
    ending: "Ending…",
  },
} as const;

/** Words and notes for the loading screens (see components/loader.tsx). */
export const loading = {
  app: { label: "Loading", note: "Just a moment." },
  signIn: { label: "Loading", note: "Opening sign in." },
  signUp: { label: "Loading", note: "Opening sign up." },
  onboarding: { label: "Getting ready", note: "Bringing back where you left off." },
  space: { label: "Loading", note: "Getting your space ready." },
  report: { label: "Loading", note: "Opening your reflection." },
  reflecting: { label: "Reflecting", note: "Looking at what you shared. Thank you for your patience." },
  room: { label: "Getting ready", note: "Preparing your room." },
} as const;

/** Home page (dashboard). "Review" is the candidate-facing word for what the report holds. */
export const home = {
  title: "Here's where you stand and what to work on next.",
  startPractice: "Start practice",
  subtitle: {
    ready: "Your latest session is ready. See what came through clearly, where you can improve, and what to work on next.",
    processing: "We're preparing your review. It will be here shortly, and your conversation is saved.",
    failed: "Your conversation is saved. Your review didn't finish, and you can try again without repeating it.",
    inProgress: "Your conversation is saved. Pick it up whenever you're ready.",
    ready_to_begin: "Your role and experience are set. Begin your conversation whenever you're ready.",
    setup: "Finish setting up your role, then begin your conversation.",
    empty: "Start with a role and a little of your experience. Mirror will take it from there.",
  },
  latest: {
    label: "Your latest review",
    completed: "Completed",
    title: "Your review is ready",
    body: "You completed the conversation for this role. Mirror has brought together what you shared, how you answered, and what the role expects.",
    read: "Open full review",
    viewSession: "Review your answers",
    signals: { clear: "Came through clearly", stronger: "Could be stronger", revisit: "Worth revisiting" },
    shorter: "From a shorter conversation, so a few areas say “not enough to say yet.”",
    steps: ["Role setup", "Conversation", "Review ready"],
    stepsAria: "Progress",
  },
  processing: {
    title: "We're preparing your review",
    body: "This usually takes a minute or two. You can leave this page. It will be here when you come back.",
    slow: "This is taking a little longer than usual. Your conversation is saved, and you can check back shortly.",
    steps: ["Role setup", "Conversation", "Preparing your review"],
  },
  failed: {
    title: "We couldn't finish your review just now",
    body: "Your conversation is saved. Mirror can try again without repeating it.",
    retry: "Try again",
    retrying: "Trying again…",
    steps: ["Role setup", "Conversation", "Review not finished"],
  },
  inProgress: {
    title: "You have a practice in progress.",
    body: "Your work is saved. Pick up where you left off.",
    cont: "Continue practice",
    end: "End and get my review",
    ending: "Ending…",
    steps: ["Role setup", "Conversation in progress", "Review"],
  },
  beginReady: {
    title: "Your practice is ready.",
    body: "Your role and experience are set. You can begin whenever you're ready.",
    begin: "Start practice",
    steps: ["Role setup", "Conversation", "Review"],
  },
  setup: {
    title: "Finish setting up this role",
    body: "Add your role and experience so your conversation can begin.",
    cont: "Complete role setup",
    steps: ["Role setup in progress", "Conversation", "Review"],
  },
  empty: {
    title: "Let's prepare for the interview you actually want.",
    body: "Tell Mirror about your experience, choose a role, and start your first practice when you're ready.",
    start: "Continue setup",
    first: "Start first practice",
  },
  next: {
    title: "Your next step",
    review: "Practice this",
    again: "Practice this role",
    another: "Prepare for another role",
    addExperienceTitle: "Add your experience",
    addExperienceBody: "Give Mirror enough context to make your practice sessions more useful.",
    addExperience: "Add your experience",
    keepGoing: "Complete another practice",
    keepGoingBody: "Complete another practice to see how your answers are developing.",
    loading: "Getting your next step ready",
  },
  came: {
    title: "How you're developing",
    subtitle: "A quick view of your latest conversation.",
    subtitleFor: (role: string, date: string) => `A quick view of your ${role} conversation on ${date}.`,
  },
  work: {
    title: "What to work on",
    subtitle: (count: number) => (count === 1 ? "1 thing from your latest session" : `${count} things from your latest session`),
    from: "From",
    cta: "Work on this",
  },
  review: {
    clear: "Coming through clearly",
    improve: "Needs more work",
    unexplored: "Not explored yet",
    unexploredBody: "We haven't asked enough about this area yet.",
    noClear: "Another practice will help Mirror understand what already comes through clearly.",
    noImprove: "Your latest review didn't identify a specific area to work on next.",
  },
  continuePreparing: {
    title: "Continue preparing",
    another: "Prepare for another role",
  },
  practicePicker: {
    title: "What do you want to prepare for?",
    body: "Choose a role to continue or start another practice.",
    another: "Another role",
    close: "Close role selection",
    preparing: "Preparing your practice…",
    failed: "We couldn't prepare that practice just now. You can try again without losing anything.",
  },
  progress: {
    experience: "Tell us about your experience",
    role: "Choose a role",
    practice: "Start your first practice",
  },
  recent: {
    title: "Recent sessions",
    subtitle: "Continue, revisit or compare your previous practice.",
    viewAll: "View all sessions",
    viewAllShort: "View all",
    empty: "Your sessions will appear here.",
    previous: "Previous session",
  },
  experience: {
    title: "Your experience",
    subtitle: "The work, projects and achievements Mirror can draw from when you practise.",
    manage: "Manage your experience",
    manageShort: "Manage",
    empty: "You haven't added any experience yet.",
    emptyCta: "Add your experience",
    updated: "Updated",
    recentlyUpdated: "Recently updated",
  },
  roles: {
    label: "Roles",
    none: "None yet",
    title: "Roles you're working toward",
    explore: "Explore roles",
    exploreShort: "Explore",
    open: "Open role",
    cont: "Continue",
    empty: "The roles you practise for will appear here.",
  },
  errors: {
    load: "We couldn't load your space just now. Your saved interviews have not been removed.",
    end: "We couldn't end the conversation just now. Please try again.",
    retry: "We couldn't try that again just now. Please try again in a moment.",
    reload: "Try again",
  },
} as const;

/** Practice: where people start, continue and revisit their interview practice. */
export const practice = {
  eyebrow: "Practice",
  title: "Your practice",
  intro: "Start where you left off, or choose something specific to work on.",
  start: "Start practice",
  continueTitle: "Continue preparing",
  lastPractised: (day: string) => `Last practised ${day}`,
  neverPractised: "Not practised yet",
  specificTitle: "Practice something specific",
  specificBody: "Every practice is a full conversation. Choosing a focus gives you something to keep in mind while you answer.",
  recommended: "Recommended",
  otherOptions: "Other things to focus on",
  previousTitle: "Previous practice",
  previousEmpty: "Your finished practice will appear here.",
  historyLabel: "Previous practice",
  empty: {
    title: "You haven't practised yet.",
    body: "Choose a role and have your first conversation whenever you feel ready.",
    action: "Start practice",
  },
  errors: {
    load: "We couldn't load your practice just now. Nothing you've done has been removed.",
    retry: "Try again",
  },
} as const;

/** The two steps of starting a practice: which role, then what to keep in mind. */
export const startPractice = {
  eyebrow: "Start practice",
  back: "Back",
  stepOf: (step: number, total: number) => `Step ${step} of ${total}`,
  roleStep: {
    title: "What do you want to prepare for?",
    body: "Choose one of your roles, or add a new one.",
    another: "Prepare for another role",
    anotherBody: "Add a role and a job description.",
    empty: "You haven't added a role yet.",
    setupNeeded: "A little setup is needed",
    ready: "Ready to practice",
  },
  focusStep: {
    title: "What would you like to practice?",
    body: "Your conversation covers the whole interview either way. A focus is a reminder Mirror shows you before you begin.",
    begin: "Start practice",
    preparing: "Preparing your practice…",
    failed: "We couldn't prepare that practice just now. You can try again without losing anything.",
  },
} as const;

/**
 * Focus options. Mirror always runs a full interview conversation; a focus is a
 * reminder the person chooses for themselves, never a change to the questions.
 */
export const practiceFocus = {
  note: "Whichever you choose, the conversation covers your whole interview. Your focus appears as a reminder before you begin.",
  reminderLabel: "Your focus for this practice",
  options: [
    {
      key: "full",
      title: "Full interview practice",
      body: "A complete conversation about your experience and the role.",
      recommended: true,
    },
    { key: "story", title: "Tell your story", body: "Walk through your background and how you got here." },
    { key: "project", title: "Explain a project", body: "Talk through one piece of work from start to finish." },
    { key: "decisions", title: "Explain your decisions", body: "Say why you chose an approach, and what you weighed up." },
    { key: "impact", title: "Show your impact", body: "Describe what changed because of your work." },
    { key: "role", title: "Role-specific questions", body: "Focus on what this particular role looks for." },
  ],
} as const;

/** My Experience: what Mirror draws on when it prepares questions. */
export const experience = {
  eyebrow: "My Experience",
  title: "My Experience",
  intro: "This is what Mirror uses to understand your background and ask more relevant questions.",
  add: "Add something",
  sections: {
    resume: "Resume",
    work: "Work",
    projects: "Projects",
    achievements: "Achievements",
    other: "Other",
  },
  enough: "Mirror has enough information to personalise your practice.",
  addProject: "Adding one recent project will help Mirror ask more specific questions.",
  addResume: "Add your resume so Mirror can prepare questions about your own experience.",
  readingResume: "Mirror is still reading your resume. Your work and projects will appear here once it's done.",
  resumeUnread: "Mirror couldn't finish reading your resume. Your file is saved, and you can replace it or try again.",
  fromResume: "From your resume",
  fromResumeNote: "Work, projects and achievements are read from your resume. Replace your resume to change them.",
  view: "View",
  replace: "Replace",
  viewDetails: "View details",
  present: "Present",
  addProjectAction: "Add a project",
  addAchievementAction: "Add an achievement",
  empty: {
    title: "Your experience is empty.",
    body: "Add a resume, job or project so Mirror can make your practice more relevant.",
    action: "Add experience",
  },
  emptyWork: "No work history has been read from your resume yet.",
  emptyProjects: "No projects yet.",
  emptyAchievements: "No achievements yet.",
  removed: "Recently removed",
  removedBody: "Removed from future practice. Practice you've already finished keeps what it used.",
  restore: "Restore",
  remove: "Remove",
  errors: {
    load: "We couldn't load your experience just now. Your saved files have not been changed.",
  },
} as const;

/** Roles a person is preparing for. */
export const roles = {
  eyebrow: "Roles",
  title: "Roles you're preparing for",
  intro: "Each role shapes the questions Mirror asks and what your review looks at.",
  add: "Prepare for another role",
  active: "Active",
  setupIncomplete: "Setup incomplete",
  notPractisedYet: "Not practised yet",
  continuePreparing: "Continue preparing",
  finishSetup: "Finish setup",
  open: "Open role",
  lastPractised: (day: string) => `Last practised ${day}`,
  empty: {
    title: "You haven't added a role yet.",
    body: "Choose a role you're preparing for to start personalised practice.",
    action: "Add a role",
  },
  errors: {
    load: "We couldn't load your roles just now. Nothing has been removed.",
  },
  detail: {
    back: "All roles",
    start: "Start practice",
    expects: {
      title: "What this role expects",
      body: "Read from the job description you shared for this role.",
      empty: "Mirror is still getting to know this role. Come back in a moment.",
      unreadable: "Mirror couldn't finish getting to know this role. You can prepare it again.",
      themes: "Likely to come up",
      mustHave: "Looked for most",
      niceToHave: "Helpful to have",
    },
    connects: {
      title: "How your experience connects",
      body: "Based on what Mirror has read from your resume.",
      empty: "Add your resume so Mirror can line your experience up with this role.",
      strong: "Strong connection",
      worth: "Worth exploring further",
      notYet: "Not yet demonstrated",
      notYetBody: "Nothing in your experience speaks to this yet.",
    },
    areas: {
      title: "Current preparation areas",
      body: "From your most recent practice for this role.",
      empty: "Complete a practice for this role to see what to work on.",
    },
    history: {
      title: "Practice history",
      empty: "You haven't practised this role yet.",
    },
  },
} as const;

/** Progress: am I getting better? */
export const progress = {
  eyebrow: "Progress",
  title: "Your Progress",
  intro: "How your answers are developing across your practice.",
  roleLabel: "Role",
  developing: {
    title: "How your answers are developing",
    body: "Four parts of a clear interview answer.",
  },
  directions: {
    IMPROVING: "Improving",
    STEADY: "Steady",
    NEEDS_MORE_PRACTICE: "Needs more practice",
  } as Record<string, string>,
  changesTitle: "Changes we've noticed",
  changesBody: "Taken from your two most recent practices for this role.",
  changesLocked: "Complete another practice for this role to see how your answers change over time.",
  noChanges: "Your two most recent practices came through in much the same way.",
  viewReview: "View review",
  historyTitle: "Your practice",
  onePractice: "One practice so far",
  empty: {
    title: "Nothing to show yet.",
    body: "Your progress will appear here after your first completed practice.",
    action: "Start practice",
  },
  pending: {
    title: "Your review is still being prepared.",
    body: "Once it's ready, this page will show how your answers are developing.",
  },
  errors: {
    load: "We couldn't load your progress just now. Nothing you've done has been removed.",
  },
  area: {
    back: "Progress",
    whatThisMeans: "What this means",
    whatWeHeard: "What we heard",
    fromYourPractice: "From your practice",
    fromYourPracticeNote: "Your own words, taken from your conversation.",
    howToImprove: "How to improve",
    practiceThis: "Practice this",
    notFound: "We couldn't find that area.",
    notExplored: "This hasn't come up enough yet, so there isn't anything to say about it.",
  },
  meanings: {
    role_understanding: {
      means: "Interviewers want to see that you understand what the role involves, and that your experience speaks to it.",
      steps: [
        "What the role is responsible for",
        "Which part of your experience matches it",
        "What you'd want to learn quickly",
      ],
    },
    examples: {
      means: "Interviewers remember specific situations far more than general statements.",
      steps: [
        "The situation, in one or two sentences",
        "What you did in it",
        "One detail only you would know",
      ],
    },
    depth: {
      means: "Interviewers often want to understand how you think, not only what you did.",
      steps: [
        "What options you had",
        "Which one you chose",
        "Why you chose it",
        "What you'd do differently now",
      ],
    },
    impact: {
      means: "Interviewers often want to understand what changed because of your work.",
      steps: [
        "What situation existed",
        "What you changed",
        "Why you chose that approach",
        "What happened afterwards",
      ],
    },
  } as Record<string, { means: string; steps: readonly string[] }>,
  heard: {
    role_understanding: "Your answers described your work. They stopped short of connecting it to what this role is looking for.",
    examples: "Your answers set out the shape of your work. They often stayed general rather than describing one specific situation.",
    depth: "Your answers described what you did. They often stopped before explaining why you chose that approach.",
    impact: "Your answers described the work and what you did clearly. They often stopped before describing the result, who benefited, or what improved.",
  } as Record<string, string>,
} as const;

/** The full review of one practice. */
export const review = {
  eyebrow: "Review",
  back: "Practice",
  overview: "Overview",
  clearTitle: "What came through clearly",
  clearEmpty: "This conversation was a little short, so there isn't a clear pattern to point to yet.",
  improveTitle: "Where you can improve",
  improveEmpty: "Your review didn't point to one area to work on next.",
  improveFrom: "From",
  answersTitle: "Your answers",
  answersBody: "Everything you were asked, in the order it came up.",
  answersEmpty: "Your conversation isn't available to read back just now.",
  answersUnavailable: "We couldn't bring back your conversation just now. The rest of your review is still here.",
  question: "Question",
  yourAnswer: "Your answer",
  noAnswer: "You moved on without answering this one.",
  cameThrough: "What came through",
  couldBeClearer: "What could be clearer",
  nothingNoted: "Nothing specific was noted for this answer.",
  nextTitle: "Your next practice",
  nextStart: "Start focused practice",
  nextMinutes: "About 8 minutes",
  practiceThis: "Practice this",
  readiness: "Where you stand",
  readinessNote: "These appear as ranges because one conversation can only show so much.",
} as const;

/** Settings: predictable, and nothing hidden here that belongs elsewhere. */
export const settings = {
  eyebrow: "Settings",
  title: "Settings",
  intro: "Your details, your practice preferences and the information Mirror has saved.",
  profile: {
    title: "Profile",
    body: "This name appears in your space. Your email is managed by the account you sign in with.",
    name: "Full name",
    email: "Email address",
    save: "Save changes",
    saving: "Saving…",
    saved: "Your profile has been updated.",
  },
  interview: {
    title: "Interview preferences",
    body: "How your practice conversations run.",
    language: "Language you'd like to practice in",
    languageNote: "Mirror speaks with you in this language where it can.",
    mode: "How you answer",
    modeValue: "Speaking, with typing available at any point",
    modeNote: "You can switch to typing during a conversation whenever you prefer.",
    saved: "Your preferences have been saved.",
  },
  privacy: {
    title: "Privacy and data",
    body: "What Mirror has saved, and where to manage it.",
    experience: "Your experience",
    experienceBody: "The resumes, projects and other work Mirror draws on.",
    history: "Your practice history",
    historyBody: "Every conversation you've had and the review that followed.",
    note: "Your resume and conversations stay private to you, and are not intentionally used to train third-party models.",
    deletion: "Removing your account",
    deletionBody: "Mirror can't remove your whole account from here yet. Write to us and we'll take care of it and confirm when it's done.",
    deletionAction: "Email us about removing your account",
  },
  notifications: {
    title: "Notifications",
    body: "Mirror doesn't send notifications yet. When your review is ready it appears on your Home page, and your conversation is always saved.",
  },
  account: {
    title: "Account",
    body: "Your sign-in is managed by the account you signed up with.",
    signOut: "Sign out",
    signingOut: "Signing out…",
  },
  errors: {
    load: "We couldn't load your settings just now. Please try again.",
    save: "We couldn't save that just now. Please try again.",
  },
} as const;

/** Help: short, because the product should explain itself. */
export const help = {
  eyebrow: "Help",
  title: "How Mirror works",
  intro: "Mirror helps you practise talking about your own experience, then shows you what came through.",
  contactLabel: "Still stuck?",
  contact: "Write to us and a person will read it.",
  contactAction: "Email support",
  sections: [
    {
      title: "How Mirror works",
      body: "You add your experience, choose a role, and have a friendly conversation. Afterwards Mirror puts together a review of what came through clearly and what to work on next.",
    },
    {
      title: "Preparing for an interview",
      body: "Add a role with its job description. Mirror reads the role and your experience together, then prepares questions about your own work rather than generic ones.",
    },
    {
      title: "Understanding your review",
      body: "Your review starts with what came through clearly, then up to three things to work on. If a conversation was short, some areas will say not explored yet. That's a normal outcome, not a problem.",
    },
    {
      title: "Managing your information",
      body: "My Experience holds everything Mirror draws on. You can add, replace and remove items at any time. Practice you've already finished keeps the version it used.",
    },
    {
      title: "Privacy",
      body: "Your resume and conversations stay private to you, and are not intentionally used to train third-party models. Mirror is a practice partner, not a hiring decision-maker.",
    },
  ],
} as const;

/** The menu behind the avatar. Not a second copy of the main navigation. */
export const profileMenu = {
  open: "Your account",
  close: "Close menu",
  profile: "Profile",
  preferences: "Interview preferences",
  account: "Account settings",
  help: "Help and support",
  signOut: "Sign out",
  signOutFailed: "We couldn't sign you out just now. Please try again.",
} as const;

/** Interview Map: what a role is likely to explore, next to what you can already show. */
export const interviewMap = {
  eyebrow: "Interview Map",
  title: "What this interview is likely to explore",
  intro: "Taken from the role and your own experience. These are likely themes, not a list of questions you will definitely get.",
  inferred: "You didn't add a job description for this role, so these themes are typical for the role rather than taken from a specific job.",
  fromJob: "From the job description",
  themesTitle: "Likely interview themes",
  strengthsTitle: "You already have useful experience for",
  strengthsEmpty: "We haven't found experience that clearly matches these themes yet.",
  areasTitle: "Prepare these areas",
  areasEmpty: "Nothing stands out as missing for this role right now. Practice will show what still needs work.",
  questionsTitle: "Questions worth preparing for",
  questionsNote: "Questions like these often come up for this kind of role. Preparing an answer helps whether or not you're asked exactly this.",
  alsoExpected: "The role also mentions",
  coverage: {
    PREPARED: "Story ready",
    EXPERIENCE: "Useful experience",
    MENTIONED: "Mentioned, not yet shown",
    MISSING: "No example yet",
  } as Record<string, string>,
  matchKinds: {
    STORY: "Your story",
    WORK: "Your work",
    PROJECT: "Your project",
    ACHIEVEMENT: "Your achievement",
    SKILL: "Named on your resume",
    TOOL: "Named on your resume",
  } as Record<string, string>,
  actions: {
    FIND_STORY: "Help me find a story",
    PRESSURE_TEST: "Pressure-test my resume",
    PRACTICE: "Practice this",
    ADD_EXPERIENCE: "Add your experience",
  } as Record<string, string>,
  states: {
    preparing: "Mirror is still getting to know this role. This page will fill in once it's done.",
    unreadable: "Mirror couldn't finish reading this role. You can prepare it again from Roles.",
    reading: "Mirror is still reading your resume, so your side of the map is empty for now.",
    unreadableResume: "Mirror couldn't read your resume, so your side of the map is empty. Replacing it in My Experience usually fixes this.",
  },
  errors: {
    load: "We couldn't load your interview map just now. Nothing has been removed.",
  },
  pressureCta: "Pressure-test my resume",
  pressureBody: "Make sure you can explain what's on your resume clearly when someone digs deeper.",
} as const;

/** The parts of one role's preparation workspace. */
export const roleWorkspace = {
  label: "Role preparation",
  map: "Interview Map",
  pressure: "Pressure-test",
} as const;

/** Home's snapshot of the current role, taken from its Interview Map. */
export const homePreparation = {
  label: "Your interview preparation",
  title: (themes: number, areas: number) =>
    areas === 0
      ? `This interview is likely to explore ${themes} ${themes === 1 ? "theme" : "themes"}.`
      : `This interview is likely to explore ${themes} ${themes === 1 ? "theme" : "themes"}. ${areas} ${areas === 1 ? "is" : "are"} worth preparing.`,
  open: "Open interview map",
  ready: "Ready to discuss",
  readyEmpty: "We haven't found experience that clearly matches this role yet.",
  prepare: "Still worth preparing",
  prepareEmpty: "Nothing stands out as missing right now.",
} as const;

/** Resume Pressure-test: explain what's on your resume clearly when someone digs deeper. */
export const pressureTest = {
  eyebrow: "Pressure-test",
  title: "Pressure-test your resume",
  intro: "Make sure you can explain what's on your resume clearly when someone digs deeper. Statements most relevant to this role come first.",
  mayAsk: "An interviewer may ask",
  howReady: "How prepared are you to explain this?",
  canExplain: "I can explain this",
  needPrepare: "I need to prepare",
  marked: { CAN_EXPLAIN: "You said you can explain this", NEEDS_PREPARATION: "Marked to prepare" } as Record<string, string>,
  start: "Pressure-test me",
  relatedTo: "Relevant to",
  where: "From your resume",
  question: (step: number, total: number) => `Question ${step} of ${total}`,
  answerLabel: "Your answer",
  answerHint: "Answer in your own words, as you would out loud. Mirror only uses what you write.",
  check: "Check my answer",
  checking: "Checking…",
  noticed: "What we noticed",
  tryFollowUp: "A follow-up you might hear",
  next: "Next question",
  finish: "Finish",
  stop: "Stop here",
  saveStory: "Save my answers as a story",
  saving: "Saving…",
  savedStory: "Open your story",
  checksNote: "These notes only say what's in your answer. They're not a grade.",
  states: {
    NO_RESUME: "Add your resume in My Experience so Mirror can find the statements worth preparing.",
    READING: "Mirror is still reading your resume. Come back in a moment.",
    UNREADABLE: "Mirror couldn't read statements from your resume. Replacing it in My Experience usually fixes this.",
  } as Record<string, string>,
  errors: {
    load: "We couldn't load your resume statements just now. Nothing has been removed.",
    save: "We couldn't save that just now. Please try again.",
    check: "We couldn't check that answer just now. Your answer is still here.",
  },
} as const;

/** My Stories: how you explain a real experience in an interview. */
export const stories = {
  eyebrow: "My Stories",
  title: "My Stories",
  intro: "Your experience is what happened. A story is how you explain it in an interview. Build a few you can tell clearly and reuse.",
  add: "Add a story",
  findOne: "Help me find a story",
  empty: {
    title: "You haven't written a story yet.",
    body: "Start from something on your resume, or let Mirror help you find an example for an area you still need to prepare.",
  },
  from: {
    MANUAL: "Written by you",
    PRESSURE_TEST: "From your resume pressure-test",
    FIND_A_STORY: "Found with Mirror's help",
    EXPERIENCE: "From your experience",
  } as Record<string, string>,
  completeness: {
    READY: "Ready to tell",
    DEVELOPING: "Developing",
    STARTED: "Needs more detail",
  } as Record<string, string>,
  nextPart: (label: string) => `Add next: ${label.toLowerCase()}`,
  sourceLabel: "Based on",
  themesLabel: "Themes",
  themesHint: "Separate themes with commas, for example: stakeholder management, pricing",
  titleLabel: "Story title",
  titleHint: "A short name you'll recognise, for example “Rebuilding the pricing model”.",
  save: "Save story",
  saving: "Saving…",
  saved: "Your story is saved.",
  edit: "Edit",
  delete: "Delete story",
  deleteTitle: "Delete this story?",
  deleteBody: "Your experience and past practice stay as they are. Only this written story is removed, and it can't be recovered.",
  cancel: "Cancel",
  confirmDelete: "Delete",
  back: "My Stories",
  parts: {
    situation: { label: "Situation", prompt: "What was going on, and why did it matter?" },
    ownership: { label: "What you owned", prompt: "Which part was yours, as opposed to the team's?" },
    actions: { label: "What you did", prompt: "The steps you took, in your own words." },
    reasoning: { label: "Why you chose that approach", prompt: "What options did you have, and why this one?" },
    trade_offs: { label: "Trade-offs", prompt: "What did you give up, or what was the risk?" },
    outcome: { label: "Outcome", prompt: "What happened afterwards?" },
    measurable_result: { label: "Measurable result", prompt: "How big was the change? A range or an estimate is fine, if you say so." },
    learning: { label: "What you learned", prompt: "What would you take into your next role?" },
    do_differently: { label: "What you'd do differently", prompt: "Looking back, what would you change?" },
  } as Record<string, { label: string; prompt: string }>,
  guide: {
    eyebrow: "Help me find a story",
    title: (theme: string) => `Find a story about ${theme.toLowerCase()}`,
    titleGeneral: "Find a story from your own experience",
    intro: "Mirror asks, you answer. Only what you write goes into the story, and you can stop at any point.",
    step: (step: number, total: number) => `Step ${step} of ${total}`,
    next: "Next",
    back: "Back",
    finish: "Save my story",
    nothingYet: "Nothing comes to mind? That's useful to know. Try a different project, a class, or work outside a job.",
    prompts: [
      { part: "situation", prompt: (theme: string) => `Think about a time ${theme.toLowerCase()} really mattered in your work, study or a project. What was going on?` },
      { part: "ownership", prompt: () => "What was your part in it, as opposed to other people's?" },
      { part: "actions", prompt: () => "What did you actually do? Walk through the steps." },
      { part: "reasoning", prompt: () => "Why did you approach it that way? Was there another option?" },
      { part: "outcome", prompt: () => "What happened in the end? Include anything you can measure, and say if it's an estimate." },
    ],
  },
  errors: {
    load: "We couldn't load your stories just now. Nothing has been removed.",
    save: "We couldn't save your story just now. Your writing is still here.",
    delete: "We couldn't delete that story just now. Please try again.",
  },
} as const;
