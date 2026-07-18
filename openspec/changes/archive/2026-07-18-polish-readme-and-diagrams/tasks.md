## 1. Diagrams

- [x] 1.1 Add a Mermaid architecture diagram (ownership boundaries + API +
  projections + outbox + worker + relay).
- [x] 1.2 Add a Mermaid saga state diagram and a sequence diagram (happy path,
  compensation, park → resolve).

## 2. Surface & processes

- [x] 2.1 Update the API list (accounts balance/freeze/close, transfers resolve)
  and the processes (`ledger-relay`); mention the saga cockpit playground.

## 3. Trade-offs

- [x] 3.1 Add a "Known trade-offs" section (append-lock tailing, in-memory-rebuilt
  projections, in-memory vs Postgres idempotency, park-awaiting-operator).

## 4. Verify

- [x] 4.1 Mermaid blocks are well-formed (```mermaid fences); README renders.
