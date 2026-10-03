/** Copy for the signed-in shell (navigation, profile menu, role switcher) and the not-found and error pages. */
export const shellCopy = {
  nav: {
    home: { label: "Home", mobileLabel: "Home" },
    plan: { label: "My plan", mobileLabel: "Plan" },
    stories: { label: "My stories", mobileLabel: "Stories" },
    practice: { label: "Practice", mobileLabel: "Practice" },
    reflect: { label: "Reflect", mobileLabel: "Reflect" },
  },
  primaryNav: "Main",
  mobileNav: "Main, mobile",
  openNav: "Open navigation",
  closeNav: "Close navigation",
  homeLink: "Mirror home",
  memberFallback: "Mirror member",
  emailFallback: "Private workspace",
  profile: {
    experience: { label: "My experience" },
    roles: { label: "Roles" },
    preferences: { label: "Preferences" },
    help: { label: "Help" },
  },
  roleSwitcher: {
    label: "Preparing for:",
    choose: "Choose a role",
    addRole: "Add a role",
    switchFailed: "We couldn't switch roles just now. Your current role is unchanged.",
  },
  notFound: {
    title: "We can't find that page",
    body: "This page does not exist or was moved.",
    home: "Go home",
  },
  error: {
    title: "This page did not load",
    body: "Part of this page didn't load just now. Your saved work is safe, and you can try again from here.",
    retry: "Try again",
    home: "Go home",
  },
} as const;
