# LOL Short-Window Last-Hit Decision Evaluation Framework (Compact)

## Abstract

This paper specifies a discrete-event model for replay analysis and short-horizon decisions. The analysis window runs from (t_0) to (T), normally covering one minion wave or 20–30 seconds. One champion is the subject (A), and the opponent is (B). The model records states, executable actions, lane events, and terminal relative value. Actions are first filtered by hard feasibility conditions, then assigned quality, and finally settled against the joint terminal changes in experience, gold, and recoverable state.

## 1. Object and horizon

The subject is (A) and the opponent is (B).

The state belief is

\[
\Omega_t=(X_t,\mathcal E_t,\Theta_t),\quad X_t=(g_t,x_t,h_t,m_t,c_t,s_t,p_t)
\]

The components (g,x,h,m,c,s,p) denote gold, experience, health resources, mana or energy, cooldown state, summoner spells and consumables, and position. (mathcal E_t) is the pending-event set and (Theta_t) contains patch, champion, item, and rune parameters. Only behavior in (t_0le tle T) is evaluated; the model does not extrapolate to the whole match.

## 2. State and event transition

Events include attacks, abilities, movement, hits, minion deaths, resource gains, and cooldown completion. State transition is

\[
x_{t+\Delta t}=F(x_t,a_t,e_t;\Theta_t),\quad e_t\sim P(\cdot\mid x_t,a_t)
\]

Wind-up, hit, recovery, and movement occupy time. Events are processed in temporal order. An unobservable event remains a probability branch; it is not replaced by zero payoff.

## 3. Last-hit opportunity and feasibility

For minion (i) and action type (r), the last-hit window is

\[
W_i^r=\{t:0<h_i(t^-)\le d_i^r(x_t)\}
\]

The executable action set is

\[
C_i^r=\{a:\operatorname{Ready}(a)\land\operatorname{Reach}(a,i)\land t_{\rm hit}(a,i)\in W_i^r\}
\]

The common feasibility gate is

\[
E(a\mid\Omega_t)=\mathbf1\{\text{version, range, cooldown, control, resource, occupation, deadline}\}
\]

If the champion is controlled, an existing action cannot be cancelled, resources are insufficient, or the hit cannot land before the death deadline, (E=0). The observed action is retained for replay, but it is excluded from the mean quality of feasible actions.

## 4. Joint scheduling and free time

A schedule (pi=(a_1,ldots,a_n)) for several targets must satisfy

\[
t_{k+1}\ge t_k+\tau_k,\quad t_k\le t_i^{\rm death},\quad \pi=(a_1,\ldots,a_n)
\]

Here (	au_k) is the time occupied by action (k). After preserving the death order and remaining last-hit windows, the subject's free time is

\[
F_A(\pi)=\{t\in[t_0,T]:\pi\text{ preserves the scheduled minion deaths and hit windows}\}
\]

Harassment during free time enters the pressure layer only when it preserves the scheduled last hits.

## 5. Conditional quality layers

Action quality is determined by the feasibility gate and the available quality layers:

\[
Q(a)=E(a\mid\Omega_t)\frac{\sum_{j\in J(a)}w_jq_j(a)}{\sum_{j\in J(a)}w_j},\quad q_j\in[-1,1]
\]

\[
\operatorname{cov}(a)=\frac{\sum_{j\in J(a)}w_j}{\sum_{j\in J_{\rm all}}w_j}
\]

Missing layers are removed from the denominator and reported through coverage. Typical layers are:

\[
q_{\rm time}=\operatorname{clip}\left(2\frac{\sigma_t}{\sigma_{\max}}-1,-1,1\right)
\]

\[
R_{\rm eff}(a)=\begin{cases}R(a)&\text{if available and controllable}\\0&\text{otherwise}\end{cases}
\]

\[
q_{\rm edge}=2\operatorname{clip}\left(1-\frac{|d-R_{\rm eff}|}{\delta},0,1\right)-1
\]

Here (sigma_t) is the remaining time before impact or the death deadline, (d) is observed distance, and (delta) is the edge tolerance. A zero effective range prevents an unavailable attack or ability from being treated as a distance advantage. Attack, ability, and edge layers are evaluated in that order when the corresponding event is available; ability hit results affect the relevant branch and terminal state.

## 6. Terminal relative value

The terminal comparison uses changes from the beginning of the window:

\[
\Delta z_k=(z_{A,k}(T)-z_{A,k}(t_0))-(z_{B,k}(T)-z_{B,k}(t_0))
\]

Here (z_k) may be gold, experience, health, mana or energy, cooldown reserve, or summoner-spell reserve. Recoverable state is evaluated by its recoverable amount at the terminal point rather than by raw percentages:

\[
r_k=\frac{\min\{M_k,z_k(T)+\rho_k(T)\}-z_k(T)}{M_k}
\]

\[
V_{\rm end}=\sum_k w_k\widetilde{\Delta z_k},\quad \sum_k w_k=1
\]

(widetilde{Delta z_k}) is the normalized relative increment with its sign oriented toward available value. Gold and experience gained are positive; health, mana, cooldown, and summoner-spell expenditure are negative. A result already counted as last-hit value is not counted again in terminal value.

## 7. Probability branches and short-horizon decisions

The branch value of candidate action (a) is

\[
V(a)=\sum_b p_bV_b-\lambda\operatorname{CVaR}_{\alpha}(-V_b)+\nu\operatorname{VOI}(a)-\kappa C_{\rm exec}(a)
\]

The probability (p_b) covers hit, miss, minion-order, and trigger branches. Risk changes branch value; it is not a direct behavior-quality penalty. An information action is retained only when its expected information value exceeds its deadline loss.

## 8. Component scores

If the theoretical last-hit ceiling is (N_{\rm cs}^{\max}), the last-hit score is

\[
S_{\rm cs}=100\min\left(1,\frac{N_{\rm cs}}{N_{\rm cs}^{\max}}\right)
\]

The strategy score combines resource acquisition, experience acquisition, pressure during last-hit intervals, and terminal relative state:

\[
S_{\rm strategy}=w_{\rm cs}S_{\rm cs}+w_{\rm xp}S_{\rm xp}+w_{\rm pressure}S_{\rm pressure}+w_{\rm end}S_{\rm end},\quad \sum w=1
\]

The execution score is the normalized result of the available quality layers:

\[
S_{\rm execution}=100\frac{Q+1}{2}
\]

Strategy and execution retain equal weight:

\[
S_{\rm total}=0.5S_{\rm strategy}+0.5S_{\rm execution}
\]

The report includes component scores, coverage, feasibility, the terminal vector, and an uncertainty interval. The total score does not replace component explanations.

## 9. Output and scope

At minimum, an action or event chain returns:

```json
{
  "eligible": true,
  "layers": {"timing": 0.72, "conversion": 0.64, "endpoint": 0.81},
  "coverage": 0.91,
  "endpoint_vector": {},
  "violations": [],
  "interval": [61.0, 74.0]
}
```

Champion, item, rune, and minion patch data are inputs. Special mechanics may be supplied as observed trigger state, stacks, cooldown, and hit probability; a separate decision rule for every champion is unnecessary. The workbench, video sampling, and pixel measurement are data-preparation tools and do not change the model definition.

## 10. Replay explanation

The report identifies the feasible window used or missed; the missed time, distance, or attack-phase margin; whether minion timing changed; whether the opponent actually paid health, mana, cooldown, or summoner-spell cost; and how these changes entered terminal relative value. Unsupported behavior remains a probability branch and is reported as an interval rather than a single deterministic conclusion.
