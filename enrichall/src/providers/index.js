import { apollo } from './apollo.js';
import { hunter } from './hunter.js';
import { snov } from './snov.js';
import { rocketreach } from './rocketreach.js';
import { prospeo } from './prospeo.js';
import { dropcontact } from './dropcontact.js';

export const PROVIDERS = {
  apollo,
  hunter,
  snov,
  rocketreach,
  prospeo,
  dropcontact
};

export const PROVIDER_NAMES = Object.keys(PROVIDERS);
