/**
 * Prisma client singleton for database access.
 *
 * TODO: Initialize with actual Prisma client once schema is migrated
 */

// import { PrismaClient } from "@prisma/client";

// const globalForPrisma = globalThis as unknown as {
//   prisma: PrismaClient | undefined;
// };

// export const prisma =
//   globalForPrisma.prisma ??
//   new PrismaClient({
//     log:
//       process.env.NODE_ENV === "development"
//         ? ["query", "error", "warn"]
//         : ["error"],
//   });

// if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;

// Stub types for wireframe MVP
interface CreateData {
  data: Record<string, unknown>;
}

interface UpdateData {
  data: Record<string, unknown>;
}

// Stub for wireframe MVP
export const prisma = {
  chatSession: {
    create: async ({ data }: CreateData) => ({ id: crypto.randomUUID(), ...data }),
    findUnique: async () => null,
  },
  chatMessage: {
    create: async ({ data }: CreateData) => ({ id: crypto.randomUUID(), ...data }),
    findMany: async () => [],
  },
  agentTask: {
    create: async ({ data }: CreateData) => ({ id: crypto.randomUUID(), ...data }),
    findUnique: async () => null,
    update: async ({ data }: UpdateData) => data,
  },
};
