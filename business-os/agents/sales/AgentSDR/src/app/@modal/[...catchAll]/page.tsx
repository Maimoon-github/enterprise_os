/**
 * Clears the pop-up slot on every other navigation. Without it the slot keeps
 * its last state on a soft navigation, so a link followed from inside Settings
 * to another page would leave the pop-up open over it.
 */
export default function NoModal() {
  return null;
}
